from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from src.core.base_module import (
    BaseSAPModule, 
    SAPTransaction, 
    TransactionStatus,
    ValidationException
)


@dataclass
class VendorInvoice:
    """Vendor Invoice data structure"""
    vendor_code: str
    invoice_number: str
    invoice_date: str
    posting_date: str
    amount: float
    currency: str = "USD"
    payment_terms: str = "0001"
    tax_code: str = "I0"
    gl_account: str = ""
    cost_center: str = ""
    reference: str = ""
    text: str = ""


class AccountsPayable(BaseSAPModule):
    """
    Accounts Payable automation for FI module
    Handles vendor invoice posting (FB60), payment processing
    """
    
    def __init__(self, connector):
        super().__init__(connector, "FI-AP")
        self.company_code = "1000"  # Default, can be configured
    
    def validate_data(self, data: Dict) -> tuple[bool, List[str]]:
        """Validate vendor invoice data"""
        errors = []
        
        required_fields = [
            'vendor_code', 'invoice_number', 'invoice_date',
            'posting_date', 'amount', 'currency'
        ]
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate amount
        if data.get('amount', 0) <= 0:
            errors.append("Invoice amount must be greater than 0")
        
        # Validate dates
        try:
            if data.get('invoice_date'):
                self.format_sap_date(data['invoice_date'])
            if data.get('posting_date'):
                self.format_sap_date(data['posting_date'])
        except ValueError as e:
            errors.append(f"Invalid date format: {e}")
        
        # Validate vendor exists
        if data.get('vendor_code'):
            if not self._vendor_exists(data['vendor_code']):
                errors.append(f"Vendor {data['vendor_code']} not found")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def create(self, data: Dict) -> str:
        """
        Post vendor invoice using BAPI
        
        Args:
            data: Invoice data dictionary
        
        Returns:
            SAP document number
        """
        # Validate data
        is_valid, errors = self.validate_data(data)
        if not is_valid:
            raise ValidationException("FI-AP", f"Validation failed: {errors}")
        
        # Create invoice object
        invoice = VendorInvoice(**data)
        
        # Prepare BAPI parameters
        doc_header = {
            'USERNAME': 'AUTOMATION',
            'COMP_CODE': self.company_code,
            'DOC_DATE': self.format_sap_date(invoice.invoice_date),
            'PSTNG_DATE': self.format_sap_date(invoice.posting_date),
            'DOC_TYPE': 'KR',  # Vendor invoice
            'REF_DOC_NO': invoice.invoice_number,
            'HEADER_TXT': invoice.text
        }
        
        # Vendor line item
        vendor_item = {
            'ITEMNO_ACC': '1',
            'VENDOR_NO': invoice.vendor_code,
            'COMP_CODE': self.company_code,
            'PMNTTRMS': invoice.payment_terms,
            'BLINE_DATE': self.format_sap_date(invoice.posting_date),
            'ALLOC_NMBR': invoice.reference
        }
        
        # Currency data for vendor
        vendor_currency = {
            'ITEMNO_ACC': '1',
            'CURRENCY': invoice.currency,
            'AMT_DOCCUR': invoice.amount
        }
        
        # GL account line item
        gl_item = {
            'ITEMNO_ACC': '2',
            'GL_ACCOUNT': invoice.gl_account or '400000',
            'COMP_CODE': self.company_code,
            'COSTCENTER': invoice.cost_center,
            'ITEM_TEXT': invoice.text,
            'TAX_CODE': invoice.tax_code
        }
        
        # Currency data for GL
        gl_currency = {
            'ITEMNO_ACC': '2',
            'CURRENCY': invoice.currency,
            'AMT_DOCCUR': -invoice.amount  # Negative for GL
        }
        
        try:
            # Call BAPI to post invoice
            result = self.call_bapi(
                'BAPI_ACC_DOCUMENT_POST',
                DOCUMENTHEADER=doc_header,
                ACCOUNTPAYABLE=[vendor_item],
                ACCOUNTGL=[gl_item],
                CURRENCYAMOUNT=[vendor_currency, gl_currency]
            )
            
            # Check for errors
            messages = self.parse_sap_return_messages(
                result.get('RETURN', []) if isinstance(result.get('RETURN'), list) 
                else [result.get('RETURN', {})]
            )
            
            if messages['has_errors']:
                raise Exception(f"Invoice posting failed: {messages['errors']}")
            
            # Get document number
            doc_number = result.get('OBJ_KEY', '')
            
            # Commit transaction
            self.commit_transaction()
            
            # Log transaction
            transaction = SAPTransaction(
                transaction_id=f"FI-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                module="FI-AP",
                transaction_type="VENDOR_INVOICE",
                status=TransactionStatus.COMPLETED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by="AUTOMATION",
                data=data,
                sap_document_number=doc_number
            )
            self.log_transaction(transaction)
            
            logger.info(f"Invoice posted successfully: {doc_number}")
            return doc_number
            
        except Exception as e:
            logger.error(f"Failed to post invoice: {e}")
            self.rollback_transaction()
            raise
    
    def read(self, document_number: str) -> Dict:
        """
        Read vendor invoice document
        
        Args:
            document_number: SAP document number
        
        Returns:
            Invoice data dictionary
        """
        try:
            # Read document header
            result = self.call_bapi(
                'BAPI_ACC_DOCUMENT_DISPLAY',
                DOCUMENTNUMBER=document_number,
                COMPANYCODE=self.company_code,
                FISCALYEAR=datetime.now().year
            )
            
            header = result.get('DOCUMENTHEADER', {})
            items = result.get('ACCOUNTINGDOCUMENTS', [])
            
            invoice_data = {
                'document_number': document_number,
                'document_date': header.get('DOC_DATE'),
                'posting_date': header.get('PSTNG_DATE'),
                'reference': header.get('REF_DOC_NO'),
                'items': items
            }
            
            logger.info(f"Retrieved document: {document_number}")
            return invoice_data
            
        except Exception as e:
            logger.error(f"Failed to read document {document_number}: {e}")
            raise
    
    def update(self, document_number: str, data: Dict) -> bool:
        """
        Update vendor invoice (limited fields)
        Note: SAP typically doesn't allow direct updates, requires reversal
        """
        logger.warning("Direct update not supported. Use reversal and repost.")
        return False
    
    def delete(self, document_number: str) -> bool:
        """
        Reverse/cancel vendor invoice document
        
        Args:
            document_number: SAP document number to reverse
        
        Returns:
            Success status
        """
        try:
            result = self.call_bapi(
                'BAPI_ACC_DOCUMENT_REV_POST',
                DOCUMENTNUMBER=document_number,
                COMPANYCODE=self.company_code,
                FISCALYEAR=datetime.now().year,
                REASON='01'  # Reversal reason
            )
            
            messages = self.parse_sap_return_messages([result.get('RETURN', {})])
            
            if messages['has_errors']:
                raise Exception(f"Reversal failed: {messages['errors']}")
            
            self.commit_transaction()
            logger.info(f"Document reversed: {document_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reverse document {document_number}: {e}")
            self.rollback_transaction()
            return False
    
    def _vendor_exists(self, vendor_code: str) -> bool:
        """Check if vendor exists in SAP"""
        try:
            vendors = self.read_table(
                'LFA1',
                fields=['LIFNR'],
                where_clause=f"LIFNR = '{vendor_code.zfill(10)}'"
            )
            return len(vendors) > 0
        except:
            return False
    
    def get_vendor_balance(self, vendor_code: str) -> float:
        """Get current balance for vendor"""
        try:
            result = self.call_bapi(
                'BAPI_AP_ACC_GETBALANCES',
                COMPANYCODE=self.company_code,
                VENDOR=vendor_code.zfill(10)
            )
            
            balance_data = result.get('BALANCES', {})
            return float(balance_data.get('BALANCE', 0))
            
        except Exception as e:
            logger.error(f"Failed to get vendor balance: {e}")
            return 0.0
    
    def process_payment(self, vendor_code: str, amount: float, 
                       payment_method: str = "C") -> str:
        """
        Process vendor payment
        
        Args:
            vendor_code: Vendor number
            amount: Payment amount
            payment_method: Payment method (C=Check, T=Transfer, etc.)
        
        Returns:
            Payment document number
        """
        try:
            result = self.call_bapi(
                'BAPI_ACC_DOCUMENT_POST',
                # Payment posting logic here
                # Similar to invoice posting but with bank account
            )
            
            payment_doc = result.get('OBJ_KEY', '')
            self.commit_transaction()
            
            logger.info(f"Payment processed: {payment_doc}")
            return payment_doc
            
        except Exception as e:
            logger.error(f"Payment processing failed: {e}")
            self.rollback_transaction()
            raise
    
    def get_open_items(self, vendor_code: str) -> List[Dict]:
        """Get list of open invoices for vendor"""
        try:
            open_items = self.read_table(
                'BSIK',  # Vendor open items table
                fields=['BELNR', 'GJAHR', 'BLDAT', 'BUDAT', 'WRBTR', 'WAERS'],
                where_clause=f"LIFNR = '{vendor_code.zfill(10)}'",
                max_rows=1000
            )
            
            logger.info(f"Retrieved {len(open_items)} open items for {vendor_code}")
            return open_items
            
        except Exception as e:
            logger.error(f"Failed to get open items: {e}")
            return []


# Example usage
if __name__ == "__main__":
    from src.connectors.rfc_connector import SAPRFCConnector, SAPConfig
    
    # Initialize connector
    config = SAPConfig(
        host="sap.example.com",
        client="100",
        user="SAPUSER",
        password="password"
    )
    
    connector = SAPRFCConnector(config)
    connector.connect()
    
    # Initialize FI module
    fi_ap = AccountsPayable(connector)
    
    # Post vendor invoice
    invoice_data = {
        'vendor_code': '1000',
        'invoice_number': 'INV-2024-001',
        'invoice_date': '2024-11-01',
        'posting_date': '2024-11-01',
        'amount': 5000.00,
        'currency': 'USD',
        'gl_account': '400000',
        'cost_center': 'CC1000',
        'text': 'Automated invoice posting'
    }
    
    try:
        doc_number = fi_ap.create(invoice_data)
        print(f"Invoice posted: {doc_number}")
        
        # Read the invoice
        invoice = fi_ap.read(doc_number)
        print(f"Invoice data: {invoice}")
        
        # Get vendor balance
        balance = fi_ap.get_vendor_balance('1000')
        print(f"Vendor balance: {balance}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        connector.disconnect()