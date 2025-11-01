### ✅ Change #6: Multi-Tenant Support (Multiple Companies)

#### **✅ REAL-WORLD SOLUTION:**

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