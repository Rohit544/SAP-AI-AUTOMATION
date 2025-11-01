
from pathlib import Path
from typing import Dict, Optional
import asyncio
from src.ai_engine.invoice_processor import InvoiceProcessor
from src.modules.fi.accounts_payable import AccountsPayable
from src.modules.mm.purchase_order import PurchaseOrder

class IntelligentInvoiceWorkflow:
    """
    Real-world invoice processing workflow:
    1. Receive invoice (PDF/Image)
    2. OCR extraction
    3. AI validation
    4. PO matching (if applicable)
    5. 3-way match (PO, GR, Invoice)
    6. Approval routing
    7. Post to SAP
    """
    
    def __init__(self, connector):
        self.connector = connector
        self.invoice_processor = InvoiceProcessor()
        self.fi_ap = AccountsPayable(connector)
        self.mm_po = PurchaseOrder(connector)
    
    async def process_invoice_file(self, file_path: str, metadata: Dict = None) -> Dict:
        """
        Process invoice from file (PDF or image)
        
        Args:
            file_path: Path to invoice file
            metadata: Optional metadata (email subject, sender, etc.)
        
        Returns:
            Processing result with SAP document numbers
        """
        logger.info(f"Processing invoice file: {file_path}")
        
        result = {
            'status': 'processing',
            'file': file_path,
            'extracted_data': None,
            'validation': None,
            'po_match': None,
            'three_way_match': None,
            'approval': None,
            'sap_document': None,
            'errors': []
        }
        
        try:
            # Step 1: OCR Extraction
            logger.info("Step 1: Extracting text from invoice...")
            text = self.invoice_processor.extract_text_from_image(file_path)
            
            # Step 2: AI-powered field extraction
            logger.info("Step 2: Extracting invoice fields...")
            invoice_data = self.invoice_processor.extract_invoice_fields(text)
            result['extracted_data'] = invoice_data
            
            # Add metadata if available
            if metadata:
                invoice_data['email_subject'] = metadata.get('subject', '')
                invoice_data['sender'] = metadata.get('sender', '')
            
            # Step 3: Validate extracted data
            logger.info("Step 3: Validating invoice data...")
            is_valid, validation_errors = self._validate_invoice_data(invoice_data)
            result['validation'] = {
                'is_valid': is_valid,
                'errors': validation_errors,
                'confidence': invoice_data.get('confidence', 0.0)
            }
            
            if not is_valid:
                result['status'] = 'requires_manual_review'
                result['errors'].extend(validation_errors)
                
                # Send to manual review queue
                await self._send_to_review_queue(file_path, invoice_data, validation_errors)
                return result
            
            # Step 4: Find or create vendor
            logger.info("Step 4: Vendor lookup...")
            vendor_code = self.fi_ap.get_or_create_vendor({
                'name': invoice_data.get('vendor'),
                'tax_id': invoice_data.get('vendor_tax_id'),
                'country': invoice_data.get('vendor_country', 'US')
            })
            invoice_data['vendor_code'] = vendor_code
            
            # Step 5: PO Matching (if PO number found)
            po_number = invoice_data.get('po_number')
            if po_number:
                logger.info(f"Step 5: Matching with PO {po_number}...")
                po_match = await self._match_with_po(invoice_data, po_number)
                result['po_match'] = po_match
                
                if not po_match['is_match']:
                    result['status'] = 'po_mismatch'
                    result['errors'].append(f"PO mismatch: {po_match['reason']}")
                    
                    # Send to approver
                    await self._request_approval(invoice_data, po_match)
                    return result
                
                # Step 6: 3-Way Match (PO + GR + Invoice)
                logger.info("Step 6: Performing 3-way match...")
                three_way = await self._three_way_match(invoice_data, po_match)
                result['three_way_match'] = three_way
                
                if not three_way['is_match']:
                    result['status'] = 'three_way_mismatch'
                    result['errors'].append(f"3-way mismatch: {three_way['reason']}")
                    await self._request_approval(invoice_data, three_way)
                    return result
            
            # Step 7: Check approval requirements
            logger.info("Step 7: Checking approval requirements...")
            requires_approval = self._requires_approval(invoice_data)
            
            if requires_approval:
                approval = await self._request_approval(invoice_data)
                result['approval'] = approval
                
                if approval['status'] != 'approved':
                    result['status'] = 'pending_approval'
                    return result
            
            # Step 8: Post to SAP
            logger.info("Step 8: Posting invoice to SAP...")
            sap_doc = self._post_invoice_to_sap(invoice_data)
            result['sap_document'] = sap_doc
            result['status'] = 'completed'
            
            logger.info(f"Invoice processed successfully: {sap_doc}")
            
        except Exception as e:
            logger.error(f"Invoice processing failed: {e}", exc_info=True)
            result['status'] = 'failed'
            result['errors'].append(str(e))
        
        return result
    
    def _validate_invoice_data(self, data: Dict) -> tuple[bool, List[str]]:
        """Comprehensive invoice validation"""
        errors = []
        
        # Required fields
        required = ['vendor', 'invoice_number', 'date', 'amount']
        for field in required:
            if not data.get(field):
                errors.append(f"Missing {field}")
        
        # Amount validation
        if data.get('amount'):
            try:
                amount = float(data['amount'])
                if amount <= 0:
                    errors.append("Amount must be positive")
                if amount > 1000000:  # Sanity check
                    errors.append("Amount exceeds maximum threshold")
            except ValueError:
                errors.append("Invalid amount format")
        
        # Date validation
        if data.get('date'):
            try:
                from dateutil import parser
                invoice_date = parser.parse(data['date'])
                today = datetime.now()
                
                # Invoice can't be from future
                if invoice_date > today:
                    errors.append("Invoice date is in the future")
                
                # Invoice shouldn't be too old
                if (today - invoice_date).days > 365:
                    errors.append("Invoice is over 1 year old")
                    
            except Exception as e:
                errors.append(f"Invalid date format: {e}")
        
        # Duplicate check
        if data.get('invoice_number') and data.get('vendor_code'):
            if self._is_duplicate_invoice(data['invoice_number'], data['vendor_code']):
                errors.append("Duplicate invoice number")
        
        return len(errors) == 0, errors
    
    async def _match_with_po(self, invoice_data: Dict, po_number: str) -> Dict:
        """Match invoice with purchase order"""
        try:
            po_data = self.mm_po.read(po_number)
            
            # Calculate PO total
            po_total = sum(
                item.get('quantity', 0) * item.get('price', 0)
                for item in po_data.get('items', [])
            )
            
            invoice_amount = float(invoice_data.get('amount', 0))
            
            # Allow 5% variance
            variance = abs(po_total - invoice_amount) / po_total * 100
            
            is_match = variance <= 5.0
            
            return {
                'is_match': is_match,
                'po_amount': po_total,
                'invoice_amount': invoice_amount,
                'variance_percent': variance,
                'reason': f"Variance {variance:.2f}%" if not is_match else "Match OK"
            }
            
        except Exception as e:
            return {
                'is_match': False,
                'reason': f"PO lookup failed: {e}"
            }
    
    async def _three_way_match(self, invoice_data: Dict, po_match: Dict) -> Dict:
        """Perform 3-way match: PO + Goods Receipt + Invoice"""
        try:
            po_number = invoice_data.get('po_number')
            
            # Get goods receipts for PO
            gr_docs = self.read_table(
                'MKPF',
                fields=['MBLNR', 'MJAHR', 'BUDAT'],
                where_clause=f"EBELN = '{po_number}'"
            )
            
            if not gr_docs:
                return {
                    'is_match': False,
                    'reason': "No goods receipt found for PO"
                }
            
            # Check if quantities match
            # (Detailed logic omitted for brevity)
            
            return {
                'is_match': True,
                'gr_documents': [doc['MBLNR'] for doc in gr_docs],
                'reason': "3-way match successful"
            }
            
        except Exception as e:
            return {
                'is_match': False,
                'reason': f"3-way match failed: {e}"
            }
    
    def _requires_approval(self, invoice_data: Dict) -> bool:
        """Determine if invoice requires manual approval"""
        amount = float(invoice_data.get('amount', 0))
        
        # Check approval thresholds from config
        threshold = self.fi_ap.config.get('FI.approval.manager_approval_above', 10000)
        
        return amount > threshold
    
    async def _request_approval(self, invoice_data: Dict, match_data: Dict = None) -> Dict:
        """Send invoice for approval"""
        # Integration with approval system (email, Slack, custom app)
        # This is placeholder - implement your approval workflow
        
        logger.info(f"Requesting approval for invoice {invoice_data.get('invoice_number')}")
        
        # Send notification
        await self._send_approval_notification(invoice_data, match_data)
        
        return {
            'status': 'pending',
            'approver': 'manager@company.com',
            'requested_at': datetime.now().isoformat()
        }
    
    def _post_invoice_to_sap(self, invoice_data: Dict) -> str:
        """Post validated invoice to SAP"""
        return self.fi_ap.create({
            'vendor_code': invoice_data['vendor_code'],
            'invoice_number': invoice_data['invoice_number'],
            'invoice_date': invoice_data['date'],
            'posting_date': datetime.now().strftime('%Y-%m-%d'),
            'amount': float(invoice_data['amount']),
            'currency': invoice_data.get('currency', 'USD'),
            'reference': invoice_data.get('po_number', ''),
            'text': f"Auto-posted via AI: {invoice_data.get('invoice_number')}"
        })