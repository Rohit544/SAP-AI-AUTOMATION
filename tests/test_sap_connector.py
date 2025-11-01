# tests/test_sap_connector.py
import pytest
from src.sap_connector.rfc_connector import SAPRFCConnector, SAPConfig

def test_sap_config_creation():
    config = SAPConfig(
        host="test.sap.com",
        client="100",
        user="testuser",
        password="testpass"
    )
    assert config.host == "test.sap.com"
    assert config.client == "100"

# Run tests
pytest tests/test_sap_connector.py -v