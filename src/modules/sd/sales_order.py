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


# ==================== SD MODULE ====================

@dataclass
class SalesOrderItem:
    """Sales order line item"""
    material: str
    quantity: float
    plant: str
    unit: str = "EA"
    price: float = 0.0


class SalesOrder(BaseSAPModule):
    """
    Sales Order automation for SD module
    Handles sales order creation (VA01), changes, and displays
    """
    
    def __init__(self, connector):
        super().__init__(connector, "SD-SO")
        self.sales_org = "1000"
        self.distribution_channel = "10"
        self.division = "00"
    
    def validate_data(self, data: Dict) -> tuple[bool, List[str]]:
        """Validate sales order data"""
        errors = []
        
        required_fields = ['customer', 'sales_org', 'order_type', 'items']
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate items
        if data.get('items'):
            if not isinstance(data['items'], list) or len(data['items']) == 0:
                errors.append("At least one item is required")
            
            for idx, item in enumerate(data['items']):
                if not item.get('material'):
                    errors.append(f"Item {idx + 1}: Missing material")
                if not item.get('quantity') or item['quantity'] <= 0:
                    errors.append(f"Item {idx + 1}: Invalid quantity")
        
        # Validate customer
        if data.get('customer'):
            if not self._customer_exists(data['customer']):
                errors.append(f"Customer {data['customer']} not found")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def create(self, data: Dict) -> str:
        """
        Create sales order using BAPI
        
        Args:
            data: Sales order data
                {
                    'customer': '1000',
                    'sales_org': '1000',
                    'distribution_channel': '10',
                    'division': '00',
                    'order_type': 'OR',
                    'items': [
                        {'material': 'MAT001', 'quantity': 10, 'plant': '1000'},
                        ...
                    ]
                }
        
        Returns:
            Sales order number
        """
        # Validate
        is_valid, errors = self.validate_data(data)
        if not is_valid:
            raise ValidationException("SD-SO", f"Validation failed: {errors}")
        
        # Prepare header data
        order_header = {
            'DOC_TYPE': data.get('order_type', 'OR'),
            'SALES_ORG': data.get('sales_org', self.sales_org),
            'DISTR_CHAN': data.get('distribution_channel', self.distribution_channel),
            'DIVISION': data.get('division', self.division),
            'PURCH_NO_C': data.get('customer_po', ''),
            'REQ_DATE_H': self.format_sap_date(
                data.get('requested_date', datetime.now().strftime('%Y-%m-%d'))
            )
        }
        
        # Prepare partner data (customer)
        order_partners = [{
            'PARTN_ROLE': 'AG',  # Sold-to party
            'PARTN_NUMB': data['customer'].zfill(10)
        }, {
            'PARTN_ROLE': 'WE',  # Ship-to party
            'PARTN_NUMB': data['customer'].zfill(10)
        }]
        
        # Prepare item data
        order_items = []
        order_schedules = []
        
        for idx, item in enumerate(data['items'], 1):
            item_no = str(idx * 10).zfill(6)
            
            order_items.append({
                'ITM_NUMBER': item_no,
                'MATERIAL': item['material'],
                'PLANT': item['plant'],
                'TARGET_QTY': item['quantity'],
                'TARGET_QU': item.get('unit', 'EA'),
                'ITEM_CATEG': 'TAN',  # Standard item
                'BATCH': item.get('batch', '')
            })
            
            # Schedule line
            order_schedules.append({
                'ITM_NUMBER': item_no,
                'SCHED_LINE': '0001',
                'REQ_QTY': item['quantity'],
                'REQ_DATE': self.format_sap_date(
                    item.get('delivery_date', datetime.now().strftime('%Y-%m-%d'))
                )
            })
        
        try:
            # Call BAPI
            result = self.call_bapi(
                'BAPI_SALESORDER_CREATEFROMDAT2',
                ORDER_HEADER_IN=order_header,
                ORDER_PARTNERS=order_partners,
                ORDER_ITEMS_IN=order_items,
                ORDER_SCHEDULES_IN=order_schedules
            )
            
            # Check for errors
            messages = self.parse_sap_return_messages(
                result.get('RETURN', []) if isinstance(result.get('RETURN'), list)
                else [result.get('RETURN', {})]
            )
            
            if messages['has_errors']:
                raise Exception(f"Sales order creation failed: {messages['errors']}")
            
            # Get sales order number
            sales_order = result.get('SALESDOCUMENT', '')
            
            # Commit
            self.commit_transaction()
            
            # Log transaction
            transaction = SAPTransaction(
                transaction_id=f"SD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                module="SD-SO",
                transaction_type="SALES_ORDER",
                status=TransactionStatus.COMPLETED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by="AUTOMATION",
                data=data,
                sap_document_number=sales_order
            )
            self.log_transaction(transaction)
            
            logger.info(f"Sales order created: {sales_order}")
            return sales_order
            
        except Exception as e:
            logger.error(f"Failed to create sales order: {e}")
            self.rollback_transaction()
            raise
    
    def read(self, sales_order: str) -> Dict:
        """Read sales order details"""
        try:
            result = self.call_bapi(
                'BAPI_SALESORDER_GETDETAIL',
                SALESDOCUMENT=sales_order
            )
            
            header = result.get('ORDER_HEADER_IN', {})
            items = result.get('ORDER_ITEMS_IN', [])
            partners = result.get('ORDER_PARTNERS', [])
            
            order_data = {
                'sales_order': sales_order,
                'order_type': header.get('DOC_TYPE'),
                'customer': next(
                    (p['PARTN_NUMB'] for p in partners if p['PARTN_ROLE'] == 'AG'),
                    ''
                ),
                'created_on': header.get('CREATED_ON'),
                'items': items
            }
            
            logger.info(f"Retrieved sales order: {sales_order}")
            return order_data
            
        except Exception as e:
            logger.error(f"Failed to read sales order: {e}")
            raise
    
    def update(self, sales_order: str, data: Dict) -> bool:
        """Update sales order"""
        try:
            # Use BAPI_SALESORDER_CHANGE
            result = self.call_bapi(
                'BAPI_SALESORDER_CHANGE',
                SALESDOCUMENT=sales_order,
                ORDER_HEADER_INX={'UPDATEFLAG': 'U'},
                # Add change parameters
            )
            
            self.commit_transaction()
            logger.info(f"Sales order updated: {sales_order}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update sales order: {e}")
            self.rollback_transaction()
            return False
    
    def delete(self, sales_order: str) -> bool:
        """Delete/block sales order"""
        logger.warning("Sales orders cannot be deleted, only blocked")
        return False
    
    def _customer_exists(self, customer: str) -> bool:
        """Check if customer exists"""
        try:
            customers = self.read_table(
                'KNA1',
                fields=['KUNNR'],
                where_clause=f"KUNNR = '{customer.zfill(10)}'"
            )
            return len(customers) > 0
        except:
            return False
