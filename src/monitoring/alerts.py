from prometheus_client import Counter, Histogram, Gauge
import sentry_sdk
from typing import Dict
import requests

# Metrics
invoice_processed = Counter('invoices_processed_total', 'Total invoices processed')
invoice_failed = Counter('invoices_failed_total', 'Total invoices failed')
processing_time = Histogram('invoice_processing_seconds', 'Time to process invoice')
queue_size = Gauge('invoice_queue_size', 'Number of invoices in queue')

class AlertManager:
    """Send alerts for critical events"""
    
    def __init__(self):
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.pagerduty_key = os.getenv('PAGERDUTY_INTEGRATION_KEY')
    
    def send_critical_alert(self, title: str, message: str, details: Dict = None):
        """Send critical alert (PagerDuty + Slack)"""
        # Sentry
        sentry_sdk.capture_message(title, level='error', extra=details)
        
        # Slack
        self._send_slack_alert(title, message, 'danger')
        
        # PagerDuty
        self._trigger_pagerduty_incident(title, message)
    
    def _send_slack_alert(self, title: str, message: str, color: str = 'warning'):
        """Send Slack notification"""
        if not self.slack_webhook:
            return
        
        payload = {
            'attachments': [{
                'color': color,
                'title': title,
                'text': message,
                'footer': 'SAP Automation',
                'ts': int(datetime.now().timestamp())
            }]
        }
        
        try:
            requests.post(self.slack_webhook, json=payload)
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    def _trigger_pagerduty_incident(self, title: str, message: str):
        """Create PagerDuty incident for critical issues"""
        if not self.pagerduty_key:
            return
        
        payload = {
            'routing_key': self.pagerduty_key,
            'event_action': 'trigger',
            'payload': {
                'summary': title,
                'severity': 'critical',
                'source': 'SAP Automation',
                'custom_details': {'message': message}
            }
        }
        
        try:
            requests.post(
                'https://events.pagerduty.com/v2/enqueue',
                json=payload
            )
        except Exception as e:
            logger.error(f"Failed to create PagerDuty incident: {e}")

# Usage in workflow
class IntelligentInvoiceWorkflow:
    def __init__(self, connector):
        # ... existing code ...
        self.alert_manager = AlertManager()
    
    async def process_invoice_file(self, file_path: str, metadata: Dict = None) -> Dict:
        with processing_time.time():
            try:
                # ... processing code ...
                
                invoice_processed.inc()
                
                if result['status'] == 'failed':
                    invoice_failed.inc()
                    
                    # Send alert for failures
                    self.alert_manager.send_critical_alert(
                        title="Invoice Processing Failed",
                        message=f"Failed to process {file_path}",
                        details=result
                    )
                
                return result
                
            except Exception as e:
                invoice_failed.inc()
                
                # Critical error alert
                self.alert_manager.send_critical_alert(
                    title="Invoice Processing Exception",
                    message=str(e),
                    details={'file': file_path}
                )
                raise