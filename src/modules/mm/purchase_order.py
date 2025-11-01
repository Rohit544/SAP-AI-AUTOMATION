@dataclass
class PurchaseOrderItem:
    """Purchase order line item"""
    material: str
    quantity: float
    plant: str
    price: float
    unit: str = "EA"
    delivery_date: str = ""


class PurchaseOrder(BaseSAPModule):
    """
    Purchase Order automation for MM module
    Handles PO creation (ME21N), changes, and displays
    """
    
    def __init__(self, connector):
        super().__init__(connector, "MM-PO")
        self.company_code = "1000"
    
    def validate_data(self, data: Dict) -> tuple[bool, List[str]]:
        """Validate purchase order data"""
        errors = []
        
        required_fields = ['vendor', 'purchasing_org', 'items']
        
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
                if not item.get('price') or item['price'] <= 0:
                    errors.append(f"Item {idx + 1}: Invalid price")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def create(self, data: Dict) -> str:
        """
        Create purchase order using BAPI
        
        Args:
            data: PO data
                {
                    'vendor': '1000',
                    'purchasing_org': '1000',
                    'purchasing_group': '001',
                    'company_code': '1000',
                    'doc_type': 'NB',
                    'items': [
                        {
                            'material': 'MAT001',
                            'quantity': 100,
                            'price': 10.50,
                            'plant': '1000',
                            'delivery_date': '2024-12-01'
                        }
                    ]
                }
        
        Returns:
            Purchase order number
        """
        # Validate
        is_valid, errors = self.validate_data(data)
        if not is_valid:
            raise ValidationException("MM-PO", f"Validation failed: {errors}")
        
        # Prepare header
        po_header = {
            'DOC_TYPE': data.get('doc_type', 'NB'),
            'VENDOR': data['vendor'].zfill(10),
            'PURCH_ORG': data.get('purchasing_org', '1000'),
            'PUR_GROUP': data.get('purchasing_group', '001'),
            'COMP_CODE': data.get('company_code', self.company_code),
            'DOC_DATE': self.format_sap_date(datetime.now().strftime('%Y-%m-%d')),
            'VENDOR_REF': data.get('vendor_reference', '')
        }
        
        # Prepare items
        po_items = []
        po_schedules = []
        
        for idx, item in enumerate(data['items'], 1):
            item_no = str(idx * 10).zfill(5)
            
            po_items.append({
                'PO_ITEM': item_no,
                'MATERIAL': item['material'],
                'PLANT': item['plant'],
                'STGE_LOC': item.get('storage_location', ''),
                'QUANTITY': item['quantity'],
                'PO_UNIT': item.get('unit', 'EA'),
                'NET_PRICE': item['price'],
                'PRICE_UNIT': 1,
                'ACCTASSCAT': item.get('account_category', 'K')
            })
            
            # Schedule line
            delivery_date = item.get('delivery_date', 
                datetime.now().strftime('%Y-%m-%d'))
            
            po_schedules.append({
                'PO_ITEM': item_no,
                'SCHED_LINE': '0001',
                'QUANTITY': item['quantity'],
                'DELIVERY_DATE': self.format_sap_date(delivery_date)
            })
        
        try:
            # Call BAPI
            result = self.call_bapi(
                'BAPI_PO_CREATE1',
                PO_HEADER=po_header,
                PO_ITEMS=po_items,
                PO_ITEM_SCHEDULES=po_schedules
            )
            
            # Check for errors
            messages = self.parse_sap_return_messages(
                result.get('RETURN', []) if isinstance(result.get('RETURN'), list)
                else [result.get('RETURN', {})]
            )
            
            if messages['has_errors']:
                raise Exception(f"PO creation failed: {messages['errors']}")
            
            # Get PO number
            po_number = result.get('PURCHASEORDER', '')
            
            # Commit
            self.commit_transaction()
            
            # Log transaction
            transaction = SAPTransaction(
                transaction_id=f"MM-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                module="MM-PO",
                transaction_type="PURCHASE_ORDER",
                status=TransactionStatus.COMPLETED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by="AUTOMATION",
                data=data,
                sap_document_number=po_number
            )
            self.log_transaction(transaction)
            
            logger.info(f"Purchase order created: {po_number}")
            return po_number
            
        except Exception as e:
            logger.error(f"Failed to create PO: {e}")
            self.rollback_transaction()
            raise
    
    def read(self, po_number: str) -> Dict:
        """Read purchase order details"""
        try:
            result = self.call_bapi(
                'BAPI_PO_GETDETAIL',
                PURCHASEORDER=po_number
            )
            
            header = result.get('PO_HEADER', {})
            items = result.get('PO_ITEMS', [])
            
            po_data = {
                'po_number': po_number,
                'vendor': header.get('VENDOR'),
                'created_on': header.get('CREATED_ON'),
                'items': items
            }
            
            logger.info(f"Retrieved PO: {po_number}")
            return po_data
            
        except Exception as e:
            logger.error(f"Failed to read PO: {e}")
            raise
    
    def update(self, po_number: str, data: Dict) -> bool:
        """Update purchase order"""
        try:
            result = self.call_bapi(
                'BAPI_PO_CHANGE',
                PURCHASEORDER=po_number,
                # Add change parameters
            )
            
            self.commit_transaction()
            logger.info(f"PO updated: {po_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update PO: {e}")
            self.rollback_transaction()
            return False
    
    def delete(self, po_number: str) -> bool:
        """Delete purchase order"""
        logger.warning("POs cannot be deleted, only flagged for deletion")
        return False
    
    def create_goods_receipt(self, po_number: str, items: List[Dict]) -> str:
        """
        Create goods receipt for PO (MIGO)
        
        Args:
            po_number: Purchase order number
            items: List of items to receive
                [{'po_item': '00010', 'quantity': 50, 'storage_location': '0001'}]
        
        Returns:
            Material document number
        """
        # Prepare goods movement data
        gm_header = {
            'PSTNG_DATE': self.format_sap_date(datetime.now().strftime('%Y-%m-%d')),
            'DOC_DATE': self.format_sap_date(datetime.now().strftime('%Y-%m-%d'))
        }
        
        gm_code = {
            'GM_CODE': '01'  # Goods receipt for PO
        }
        
        gm_items = []
        for item in items:
            gm_items.append({
                'MATERIAL': item['material'],
                'PLANT': item['plant'],
                'STGE_LOC': item.get('storage_location', ''),
                'MOVE_TYPE': '101',  # GR for PO
                'ENTRY_QNT': item['quantity'],
                'PO_NUMBER': po_number,
                'PO_ITEM': item['po_item']
            })
        
        try:
            result = self.call_bapi(
                'BAPI_GOODSMVT_CREATE',
                GOODSMVT_HEADER=gm_header,
                GOODSMVT_CODE=gm_code,
                GOODSMVT_ITEM=gm_items
            )
            
            mat_doc = result.get('MATERIALDOCUMENT', '')
            self.commit_transaction()
            
            logger.info(f"Goods receipt posted: {mat_doc}")
            return mat_doc
            
        except Exception as e:
            logger.error(f"Failed to post goods receipt: {e}")
            self.rollback_transaction()
            raise