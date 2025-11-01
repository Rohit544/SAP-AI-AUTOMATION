"""
Procure-to-Pay Workflow - src/workflows/procure_to_pay.py
End-to-end automation combining MM and FI modules
"""

from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from enum import Enum

from src.modules.mm.purchase_order import PurchaseOrder
from src.modules.fi.accounts_payable import AccountsPayable
from src.ai_engine.process_classifier import ProcessClassifier
from src.ai_engine.anomaly_detector import AnomalyDetector


class WorkflowStatus(Enum):
    """Workflow status enumeration"""
    INITIATED = "initiated"
    PO_CREATED = "po_created"
    GOODS_RECEIVED = "goods_received"
    INVOICE_POSTED = "invoice_posted"
    PAYMENT_PROCESSED = "payment_processed"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcureToPayRequest:
    """Procure-to-pay workflow request"""
    requisition_id: str
    vendor: str
    materials: List[Dict]
    total_amount: float
    urgency: str = "normal"  # normal, urgent, emergency
    requester: str = ""
    cost_center: str = ""


class ProcureToPayWorkflow:
    """
    Complete Procure-to-Pay automation workflow
    
    Steps:
    1. Create Purchase Order (MM)
    2. Receive Goods (MM)
    3. Verify Invoice (FI + AI)
    4. Post Invoice (FI)
    5. Process Payment (FI)
    """
    
    def __init__(self, connector):
        self.connector = connector
        
        # Initialize modules
        self.mm_po = PurchaseOrder(connector)
        self.fi_ap = AccountsPayable(connector)
        
        # Initialize AI components
        self.classifier = ProcessClassifier()
        self.anomaly_detector = AnomalyDetector()
        
        # Workflow state
        self.workflow_id = None
        self.status = WorkflowStatus.INITIATED
        self.documents = {}
        
        logger.info("Procure-to-Pay workflow initialized")
    
    def execute(self, request: ProcureToPayRequest) -> Dict:
        """
        Execute complete procure-to-pay workflow
        
        Args:
            request: Workflow request data
        
        Returns:
            Workflow execution summary
        """
        self.workflow_id = f"P2P-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        logger.info(f"Starting workflow: {self.workflow_id}")
        
        summary = {
            'workflow_id': self.workflow_id,
            'status': 'in_progress',
            'steps_completed': [],
            'documents': {},
            'errors': []
        }
        
        try:
            # Step 1: AI Classification - Determine process type
            classification = self._classify_request(request)
            summary['classification'] = classification
            
            # Step 2: Create Purchase Order
            po_number = self._create_purchase_order(request)
            summary['steps_completed'].append('po_created')
            summary['documents']['po_number'] = po_number
            self.status = WorkflowStatus.PO_CREATED
            
            # Step 3: Goods Receipt (simulated - would be triggered by warehouse)
            # In real scenario, this would be a separate process
            material_doc = self._post_goods_receipt(po_number, request.materials)
            summary['steps_completed'].append('goods_received')
            summary['documents']['material_document'] = material_doc
            self.status = WorkflowStatus.GOODS_RECEIVED
            
            # Step 4: Invoice Verification with AI
            invoice_valid = self._verify_invoice_with_ai(request, po_number)
            
            if not invoice_valid:
                summary['errors'].append("Invoice verification failed - requires manual review")
                summary['status'] = 'requires_review'
                return summary
            
            # Step 5: Post Invoice
            invoice_doc = self._post_invoice(request, po_number)
            summary['steps_completed'].append('invoice_posted')
            summary['documents']['invoice_document'] = invoice_doc
            self.status = WorkflowStatus.INVOICE_POSTED
            
            # Step 6: Process Payment (based on payment terms)
            if self._should_auto_pay(request):
                payment_doc = self._process_payment(request.vendor, request.total_amount)
                summary['steps_completed'].append('payment_processed')
                summary['documents']['payment_document'] = payment_doc
                self.status = WorkflowStatus.PAYMENT_PROCESSED
            
            # Workflow completed
            self.status = WorkflowStatus.COMPLETED
            summary['status'] = 'completed'
            
            logger.info(f"Workflow {self.workflow_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Workflow {self.workflow_id} failed: {e}")
            summary['status'] = 'failed'
            summary['errors'].append(str(e))
            self.status = WorkflowStatus.FAILED
        
        return summary
    
    def _classify_request(self, request: ProcureToPayRequest) -> Dict:
        """Use AI to classify and prioritize the request"""
        try:
            features = {
                'amount': request.total_amount,
                'urgency': 0 if request.urgency == 'normal' else 1 if request.urgency == 'urgent' else 2,
                'item_count': len(request.materials),
                'vendor_category': 1  # Would lookup vendor rating
            }
            
            # Predict using AI classifier
            prediction = self.classifier.predict(features)
            
            logger.info(
                f"Request classified as: {prediction.process_type} "
                f"(confidence: {prediction.confidence:.2%})"
            )
            
            return {
                'process_type': prediction.process_type,
                'confidence': prediction.confidence,
                'recommended_action': prediction.recommended_action,
                'estimated_time': prediction.estimated_time
            }
            
        except Exception as e:
            logger.warning(f"AI classification failed, using defaults: {e}")
            return {
                'process_type': 'standard_procurement',
                'confidence': 0.5,
                'recommended_action': 'MANUAL_REVIEW',
                'estimated_time': 300
            }
    
    def _create_purchase_order(self, request: ProcureToPayRequest) -> str:
        """Create purchase order"""
        logger.info("Step 1: Creating purchase order...")
        
        po_data = {
            'vendor': request.vendor,
            'purchasing_org': '1000',
            'purchasing_group': '001',
            'company_code': '1000',
            'doc_type': 'NB',
            'items': request.materials
        }
        
        po_number = self.mm_po.create(po_data)
        self.documents['po_number'] = po_number
        
        logger.info(f"Purchase order created: {po_number}")
        return po_number
    
    def _post_goods_receipt(self, po_number: str, materials: List[Dict]) -> str:
        """Post goods receipt for purchase order"""
        logger.info("Step 2: Posting goods receipt...")
        
        # Prepare GR items
        gr_items = []
        for item in materials:
            gr_items.append({
                'material': item['material'],
                'plant': item['plant'],
                'quantity': item['quantity'],
                'po_item': item.get('po_item', '00010')
            })
        
        material_doc = self.mm_po.create_goods_receipt(po_number, gr_items)
        self.documents['material_document'] = material_doc
        
        logger.info(f"Goods receipt posted: {material_doc}")
        return material_doc
    
    def _verify_invoice_with_ai(self, request: ProcureToPayRequest, 
                                po_number: str) -> bool:
        """
        Verify invoice using AI anomaly detection
        Checks for discrepancies between PO and invoice
        """
        logger.info("Step 3: Verifying invoice with AI...")
        
        # Get PO data
        po_data = self.mm_po.read(po_number)
        
        # Calculate expected amount from PO
        expected_amount = sum(
            item.get('quantity', 0) * item.get('price', 0)
            for item in po_data.get('items', [])
        )
        
        # Check for anomalies
        variance = abs(expected_amount - request.total_amount)
        variance_percent = (variance / expected_amount * 100) if expected_amount > 0 else 0
        
        # Define tolerance
        tolerance_percent = 5.0  # 5% tolerance
        
        if variance_percent > tolerance_percent:
            logger.warning(
                f"Invoice amount variance detected: {variance_percent:.2f}% "
                f"(Expected: {expected_amount}, Actual: {request.total_amount})"
            )
            
            # Use AI anomaly detector
            transaction_data = {
                'amount': request.total_amount,
                'expected_amount': expected_amount,
                'variance_percent': variance_percent,
                'vendor': request.vendor
            }
            
            try:
                is_anomaly, score = self.anomaly_detector.detect(transaction_data)
                
                if is_anomaly:
                    logger.error(f"Anomaly detected (score: {score:.3f}). Manual review required.")
                    return False
            except:
                # If AI fails, use basic threshold
                if variance_percent > 10:
                    return False
        
        logger.info("Invoice verification passed")
        return True
    
    def _post_invoice(self, request: ProcureToPayRequest, po_number: str) -> str:
        """Post vendor invoice"""
        logger.info("Step 4: Posting vendor invoice...")
        
        invoice_data = {
            'vendor_code': request.vendor,
            'invoice_number': f"INV-{request.requisition_id}",
            'invoice_date': datetime.now().strftime('%Y-%m-%d'),
            'posting_date': datetime.now().strftime('%Y-%m-%d'),
            'amount': request.total_amount,
            'currency': 'USD',
            'gl_account': '400000',
            'cost_center': request.cost_center or 'CC1000',
            'reference': po_number,
            'text': f"Automated invoice for PO {po_number}"
        }
        
        invoice_doc = self.fi_ap.create(invoice_data)
        self.documents['invoice_document'] = invoice_doc
        
        logger.info(f"Invoice posted: {invoice_doc}")
        return invoice_doc
    
    def _should_auto_pay(self, request: ProcureToPayRequest) -> bool:
        """Determine if payment should be automatically processed"""
        # Auto-pay criteria
        if request.total_amount > 10000:
            logger.info("Amount exceeds auto-pay threshold")
            return False
        
        if request.urgency == "emergency":
            logger.info("Emergency request - requires manual approval")
            return False
        
        return True
    
    def _process_payment(self, vendor: str, amount: float) -> str:
        """Process vendor payment"""
        logger.info("Step 5: Processing payment...")
        
        payment_doc = self.fi_ap.process_payment(
            vendor_code=vendor,
            amount=amount,
            payment_method='T'  # Transfer
        )
        
        logger.info(f"Payment processed: {payment_doc}")
        return payment_doc
    
    def get_workflow_status(self) -> Dict:
        """Get current workflow status"""
        return {
            'workflow_id': self.workflow_id,
            'status': self.status.value,
            'documents': self.documents,
            'current_step': self.status.value
        }


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
    
    # Initialize workflow
    workflow = ProcureToPayWorkflow(connector)
    
    # Create workflow request
    request = ProcureToPayRequest(
        requisition_id="REQ-2024-001",
        vendor="1000",
        materials=[
            {
                'material': 'MAT001',
                'quantity': 100,
                'price': 50.00,
                'plant': '1000',
                'delivery_date': '2024-12-15'
            },
            {
                'material': 'MAT002',
                'quantity': 50,
                'price': 30.00,
                'plant': '1000',
                'delivery_date': '2024-12-15'
            }
        ],
        total_amount=6500.00,
        urgency="normal",
        requester="USER123",
        cost_center="CC1000"
    )
    
    # Execute workflow
    result = workflow.execute(request)
    
    print(f"\n{'='*50}")
    print(f"Workflow ID: {result['workflow_id']}")
    print(f"Status: {result['status']}")
    print(f"\nDocuments Created:")
    for doc_type, doc_number in result['documents'].items():
        print(f"  {doc_type}: {doc_number}")
    
    print(f"\nSteps Completed:")
    for step in result['steps_completed']:
        print(f"  ✓ {step}")
    
    if result['errors']:
        print(f"\nErrors:")
        for error in result['errors']:
            print(f"  ✗ {error}")
    print(f"{'='*50}\n")
    
    connector.disconnect()