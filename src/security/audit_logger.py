from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import hashlib

Base = declarative_base()

class AuditLog(Base):
    """Audit log table"""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    user_id = Column(String(100))
    tenant_id = Column(String(100))
    action = Column(String(100))
    module = Column(String(50))
    resource_type = Column(String(50))
    resource_id = Column(String(100))
    changes = Column(JSON)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    status = Column(String(20))

class AuditLogger:
    """Log all actions for compliance"""
    
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def log_action(self, action: str, resource_type: str, resource_id: str,
                   user_id: str, changes: Dict = None, status: str = 'success'):
        """Log user action"""
        
        # Mask sensitive data
        if changes:
            changes = self._mask_sensitive_data(changes)
        
        audit_entry = AuditLog(
            user_id=user_id,
            tenant_id=TenantContext.get_tenant(),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            status=status
        )
        
        self.session.add(audit_entry)
        self.session.commit()
    
    def _mask_sensitive_data(self, data: Dict) -> Dict:
        """Mask sensitive fields"""
        masked = data.copy()
        sensitive_fields = ['password', 'credit_card', 'ssn', 'tax_id']
        
        for field in sensitive_fields:
            if field in masked:
                masked[field] = '***MASKED***'
        
        return masked

# Usage
audit_logger = AuditLogger(os.getenv('DATABASE_URL'))

class AccountsPayable(BaseSAPModule):
    def create(self, data: Dict) -> str:
        # Log before action
        audit_logger.log_action(
            action='CREATE_INVOICE',
            resource_type='VENDOR_INVOICE',
            resource_id=data.get('invoice_number'),
            user_id=current_user.id,
            changes={'amount': data['amount'], 'vendor': data['vendor_code']},
            status='started'
        )
        
        try:
            result = # ... post invoice ...
            
            # Log success
            audit_logger.log_action(
                action='CREATE_INVOICE',
                resource_type='VENDOR_INVOICE',
                resource_id=result,
                user_id=current_user.id,
                status='success'
            )
            
            return result
            
        except Exception as e:
            # Log failure
            audit_logger.log_action(
                action='CREATE_INVOICE',
                resource_type='VENDOR_INVOICE',
                resource_id=data.get('invoice_number'),
                user_id=current_user.id,
                status='failed'
            )
            raise