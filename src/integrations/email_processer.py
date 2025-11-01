import imaplib
import email
from email.header import decode_header
from pathlib import Path
from typing import List, Dict
import asyncio

class EmailInvoiceProcessor:
    """
    Process invoices from email automatically
    Checks inbox, downloads attachments, processes invoices
    """
    
    def __init__(self, workflow):
        self.workflow = workflow
        self.imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.inbox_folder = 'INBOX/Invoices'  # Dedicated folder
    
    async def monitor_inbox(self, interval: int = 60):
        """Monitor inbox for new invoices"""
        logger.info(f"Starting email monitor (checking every {interval}s)")
        
        while True:
            try:
                await self.check_for_new_invoices()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Email monitoring error: {e}")
                await asyncio.sleep(300)  # Wait 5 min on error
    
    async def check_for_new_invoices(self):
        """Check inbox for unread invoice emails"""
        try:
            # Connect to email server
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_user, self.email_password)
            mail.select(self.inbox_folder)
            
            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            
            if status != 'OK':
                logger.warning("No new emails")
                return
            
            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} new emails")
            
            for email_id in email_ids:
                await self.process_email(mail, email_id)
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            logger.error(f"Failed to check emails: {e}")
    
    async def process_email(self, mail, email_id):
        """Process single email with invoice"""
        try:
            # Fetch email
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                return
            
            # Parse email
            email_body = msg_data[0][1]
            message = email.message_from_bytes(email_body)
            
            # Extract metadata
            subject = self._decode_header(message['Subject'])
            sender = self._decode_header(message['From'])
            
            logger.info(f"Processing email from {sender}: {subject}")
            
            metadata = {
                'subject': subject,
                'sender': sender,
                'date': message['Date']
            }
            
            # Process attachments
            for part in message.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                
                if part.get('Content-Disposition') is None:
                    continue
                
                filename = part.get_filename()
                
                if filename and self._is_invoice_file(filename):
                    logger.info(f"Found invoice attachment: {filename}")
                    
                    # Save attachment
                    filepath = self._save_attachment(part, filename)
                    
                    # Process invoice
                    result = await self.workflow.process_invoice_file(
                        filepath,
                        metadata
                    )
                    
                    # Send confirmation email
                    await self._send_confirmation(sender, result)
            
            # Mark as read
            mail.store(email_id, '+FLAGS', '\\Seen')
            
        except Exception as e:
            logger.error(f"Failed to process email: {e}")
    
    def _is_invoice_file(self, filename: str) -> bool:
        """Check if file is likely an invoice"""
        filename_lower = filename.lower()
        return any([
            filename_lower.endswith('.pdf'),
            filename_lower.endswith('.png'),
            filename_lower.endswith('.jpg'),
            'invoice' in filename_lower,
            'bill' in filename_lower
        ])
    
    def _save_attachment(self, part, filename: str) -> str:
        """Save email attachment to disk"""
        filepath = f"temp/invoices/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            f.write(part.get_payload(decode=True))
        
        return filepath

# Run email monitor
async def main():
    from src.workflows.invoice_processing_workflow import IntelligentInvoiceWorkflow
    from src.connectors.rfc_connector import SAPRFCConnector
    
    connector = SAPRFCConnector(config)
    connector.connect()
    
    workflow = IntelligentInvoiceWorkflow(connector)
    email_processor = EmailInvoiceProcessor(workflow)
    
    await email_processor.monitor_inbox()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### ✅ Change #6: Multi-Tenant Support (Multiple Companies)

#### **✅ REAL-WORLD SOLUTION:**
```python
# src/core/tenant_manager.py

from typing import Dict, Optional
import threading

class TenantContext:
    """Thread-local tenant context"""
    _context = threading.local()
    
    @classmethod
    def set_tenant(cls, tenant_id: str, company_code: str):
        cls._context.tenant_id = tenant_id
        cls._context.company_code = company_code
    
    @classmethod
    def get_tenant(cls) -> str:
        return getattr(cls._context, 'tenant_id', None)
    
    @classmethod
    def get_company_code(cls) -> str:
        return getattr(cls._context, 'company_code', None)

class TenantManager:
    """Manage multiple SAP systems/clients"""
    
    def __init__(self):
        self.tenants = self._load_tenant_configs()
    
    def _load_tenant_configs(self) -> Dict:
        """Load configurations for all tenants"""
        # Load from database or config file
        return {
            'company_a': {
                'sap_host': 'sap-a.company.com',
                'sap_client': '100',
                'company_code': '1000',
                'currency': 'USD',
                'country': 'US'
            },
            'company_b': {
                'sap_host': 'sap-b.company.com',
                'sap_client': '200',
                'company_code': '2000',
                'currency': 'EUR',
                'country': 'DE'
            }
        }
    
    def get_connector(self, tenant_id: str):
        """Get SAP connector for specific tenant"""
        config = self.tenants.get(tenant_id)
        if not config:
            raise ValueError(f"Unknown tenant: {tenant_id}")
        
        from src.connectors.rfc_connector import SAPRFCConnector, SAPConfig
        
        sap_config = SAPConfig(
            host=config['sap_host'],
            client=config['sap_client'],
            user=os.getenv(f'{tenant_id.upper()}_USER'),
            password=os.getenv(f'{tenant_id.upper()}_PASSWORD')
        )
        
        connector = SAPRFCConnector(sap_config)
        connector.connect()
        return connector

# Usage in API
from fastapi import Depends, Header, HTTPException

async def get_tenant_from_header(x_tenant_id: str = Header(...)) -> str:
    """Extract tenant from header"""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID required")
    return x_tenant_id

@router.post("/invoice")
async def create_invoice(
    invoice: InvoiceRequest,
    tenant_id: str = Depends(get_tenant_from_header)
):
    """Create invoice for specific tenant"""
    TenantContext.set_tenant(tenant_id, tenant_id)
    
    tenant_manager = TenantManager()
    connector = tenant_manager.get_connector(tenant_id)
    
    fi_ap = AccountsPayable(connector)
    result = fi_ap.create(invoice.dict())
    
    return {"document_number": result}