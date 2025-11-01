from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from enum import Enum


class TransactionStatus(Enum):
    """Transaction status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SAPTransaction:
    """Base transaction data structure"""
    transaction_id: str
    module: str
    transaction_type: str
    status: TransactionStatus
    created_at: datetime
    updated_at: datetime
    created_by: str
    data: Dict
    error_message: Optional[str] = None
    sap_document_number: Optional[str] = None


class BaseSAPModule(ABC):
    """
    Abstract base class for all SAP modules
    Provides common functionality and interface
    """
    
    def __init__(self, connector, module_name: str):
        """
        Initialize SAP module
        
        Args:
            connector: SAP connector instance (RFC/REST/GUI)
            module_name: Name of the SAP module (FI, SD, MM, etc.)
        """
        self.connector = connector
        self.module_name = module_name
        self.transactions: List[SAPTransaction] = []
        
        logger.info(f"Initialized {module_name} module")
    
    @abstractmethod
    def validate_data(self, data: Dict) -> tuple[bool, List[str]]:
        """
        Validate input data before processing
        
        Returns:
            (is_valid, list_of_errors)
        """
        pass
    
    @abstractmethod
    def create(self, data: Dict) -> str:
        """
        Create a new document/transaction
        
        Returns:
            Document number or transaction ID
        """
        pass
    
    @abstractmethod
    def read(self, document_number: str) -> Dict:
        """
        Read/retrieve a document
        
        Returns:
            Document data as dictionary
        """
        pass
    
    @abstractmethod
    def update(self, document_number: str, data: Dict) -> bool:
        """
        Update an existing document
        
        Returns:
            Success status
        """
        pass
    
    @abstractmethod
    def delete(self, document_number: str) -> bool:
        """
        Delete/cancel a document
        
        Returns:
            Success status
        """
        pass
    
    def log_transaction(self, transaction: SAPTransaction):
        """Log transaction for audit trail"""
        self.transactions.append(transaction)
        logger.info(
            f"Transaction logged: {transaction.transaction_id} "
            f"[{transaction.status.value}]"
        )
    
    def get_transaction_history(self, 
                               filter_status: Optional[TransactionStatus] = None
                               ) -> List[SAPTransaction]:
        """Get transaction history with optional filtering"""
        if filter_status:
            return [t for t in self.transactions if t.status == filter_status]
        return self.transactions
    
    def call_bapi(self, bapi_name: str, **params) -> Dict:
        """
        Wrapper for calling SAP BAPI
        Includes error handling and logging
        """
        try:
            logger.info(f"Calling BAPI: {bapi_name}")
            result = self.connector.call_function(bapi_name, **params)
            
            # Check for BAPI return messages
            if 'RETURN' in result:
                return_msg = result['RETURN']
                if isinstance(return_msg, dict):
                    msg_type = return_msg.get('TYPE', '')
                    if msg_type in ['E', 'A']:  # Error or Abort
                        raise Exception(
                            f"BAPI Error: {return_msg.get('MESSAGE', 'Unknown error')}"
                        )
            
            logger.info(f"BAPI {bapi_name} executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"BAPI {bapi_name} failed: {e}")
            raise
    
    def commit_transaction(self):
        """Commit SAP transaction"""
        try:
            self.call_bapi('BAPI_TRANSACTION_COMMIT', WAIT='X')
            logger.info("Transaction committed")
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            raise
    
    def rollback_transaction(self):
        """Rollback SAP transaction"""
        try:
            self.call_bapi('BAPI_TRANSACTION_ROLLBACK')
            logger.info("Transaction rolled back")
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise
    
    def read_table(self, table_name: str, fields: List[str] = None,
                   where_clause: str = "", max_rows: int = 500) -> List[Dict]:
        """
        Generic table read function
        Used by all modules to read SAP tables
        """
        return self.connector.read_table(
            table_name=table_name,
            fields=fields,
            where_clause=where_clause,
            max_rows=max_rows
        )
    
    def format_sap_date(self, date_str: str) -> str:
        """
        Convert date to SAP format (YYYYMMDD)
        
        Args:
            date_str: Date in various formats
        
        Returns:
            Date in SAP format
        """
        from dateutil import parser
        try:
            dt = parser.parse(date_str)
            return dt.strftime('%Y%m%d')
        except:
            raise ValueError(f"Invalid date format: {date_str}")
    
    def format_sap_amount(self, amount: float, decimal_places: int = 2) -> str:
        """Format amount for SAP (remove decimal point)"""
        return str(int(amount * (10 ** decimal_places)))
    
    def parse_sap_return_messages(self, return_table: List[Dict]) -> Dict:
        """
        Parse SAP RETURN table structure
        
        Returns:
            {
                'has_errors': bool,
                'errors': list,
                'warnings': list,
                'info': list
            }
        """
        result = {
            'has_errors': False,
            'errors': [],
            'warnings': [],
            'info': []
        }
        
        for msg in return_table:
            msg_type = msg.get('TYPE', '')
            message = msg.get('MESSAGE', '')
            
            if msg_type in ['E', 'A']:
                result['has_errors'] = True
                result['errors'].append(message)
            elif msg_type == 'W':
                result['warnings'].append(message)
            elif msg_type in ['I', 'S']:
                result['info'].append(message)
        
        return result
    
    def batch_process(self, data_list: List[Dict], 
                     process_function: callable) -> Dict:
        """
        Process multiple records in batch
        
        Args:
            data_list: List of data dictionaries
            process_function: Function to process each record
        
        Returns:
            Summary of batch processing
        """
        results = {
            'total': len(data_list),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for idx, data in enumerate(data_list, 1):
            try:
                result = process_function(data)
                results['successful'] += 1
                results['details'].append({
                    'index': idx,
                    'status': 'success',
                    'result': result
                })
                logger.info(f"Batch item {idx}/{len(data_list)} processed successfully")
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'index': idx,
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"Batch item {idx}/{len(data_list)} failed: {e}")
        
        logger.info(
            f"Batch processing complete: "
            f"{results['successful']} successful, "
            f"{results['failed']} failed"
        )
        
        return results
    
    def get_module_info(self) -> Dict:
        """Get module information"""
        return {
            'module': self.module_name,
            'transactions_count': len(self.transactions),
            'last_activity': self.transactions[-1].updated_at if self.transactions else None
        }


class ModuleException(Exception):
    """Base exception for module operations"""
    def __init__(self, module: str, message: str):
        self.module = module
        self.message = message
        super().__init__(f"[{module}] {message}")


class ValidationException(ModuleException):
    """Exception raised when data validation fails"""
    pass


class SAPConnectionException(ModuleException):
    """Exception raised when SAP connection fails"""
    pass


class DocumentNotFoundException(ModuleException):
    """Exception raised when document is not found"""
    pass