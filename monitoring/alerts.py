"""
Alert System for Fraud Detection
Monitors fraud alerts and triggers notifications for critical events
"""

import time
import logging
from datetime import datetime, timedelta
import psycopg2
import redis
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlertSystem:
    """Alert system for fraud detection"""
    
    def __init__(self, postgres_conn_str=None, redis_host='localhost'):
        """Initialize alert system"""
        self.postgres_conn_str = postgres_conn_str or \
            "dbname=frauddb user=frauduser password=fraudpass host=localhost port=5432"
        
        self.redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
        
        # Alert thresholds
        self.thresholds = {
            'high_fraud_score': 0.95,
            'high_amount': 5000.0,
            'rapid_frauds': 10,  # Number of frauds in short time
            'fraud_rate_spike': 0.15  # Fraud rate threshold
        }
        
        logger.info("Alert system initialized")
    
    def get_postgres_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(self.postgres_conn_str)
    
    def check_high_value_fraud(self):
        """Check for high-value fraudulent transactions"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            query = """
                SELECT transaction_id, user_id, amount, fraud_score, merchant
                FROM fraud_alerts
                WHERE detection_time >= NOW() - INTERVAL '5 minutes'
                  AND amount > %s
                  AND is_fraud = TRUE
                  AND alert_status = 'pending'
                ORDER BY amount DESC
            """
            cur.execute(query, (self.thresholds['high_amount'],))
            
            high_value_frauds = cur.fetchall()
            
            if high_value_frauds:
                for fraud in high_value_frauds:
                    self.trigger_alert(
                        alert_type='HIGH_VALUE_FRAUD',
                        severity='CRITICAL',
                        message=f"High-value fraud detected: ${fraud[2]:.2f} for user {fraud[1]}",
                        details={
                            'transaction_id': fraud[0],
                            'user_id': fraud[1],
                            'amount': fraud[2],
                            'fraud_score': fraud[3],
                            'merchant': fraud[4]
                        }
                    )
            
            cur.close()
            conn.close()
            
            return len(high_value_frauds)
            
        except Exception as e:
            logger.error(f"Error checking high-value frauds: {e}")
            return 0
    
    def check_fraud_rate_spike(self):
        """Check for sudden spike in fraud rate"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            # Get fraud rate in last 10 minutes
            query = """
                WITH recent_data AS (
                    SELECT 
                        COUNT(DISTINCT t.transaction_id) as total_tx,
                        COUNT(DISTINCT f.transaction_id) as fraud_tx
                    FROM transactions t
                    LEFT JOIN fraud_alerts f ON t.transaction_id = f.transaction_id 
                        AND f.is_fraud = TRUE
                    WHERE t.created_at >= NOW() - INTERVAL '10 minutes'
                )
                SELECT 
                    total_tx,
                    fraud_tx,
                    CASE WHEN total_tx > 0 
                         THEN CAST(fraud_tx AS FLOAT) / total_tx 
                         ELSE 0 
                    END as fraud_rate
                FROM recent_data
            """
            cur.execute(query)
            result = cur.fetchone()
            
            if result and result[2] > self.thresholds['fraud_rate_spike']:
                self.trigger_alert(
                    alert_type='FRAUD_RATE_SPIKE',
                    severity='HIGH',
                    message=f"Fraud rate spike detected: {result[2]*100:.2f}%",
                    details={
                        'total_transactions': result[0],
                        'fraud_transactions': result[1],
                        'fraud_rate': result[2]
                    }
                )
            
            cur.close()
            conn.close()
            
            return result[2] if result else 0
            
        except Exception as e:
            logger.error(f"Error checking fraud rate: {e}")
            return 0
    
    def check_rapid_fraud_sequence(self):
        """Check for rapid sequence of frauds from same user"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            query = """
                SELECT user_id, COUNT(*) as fraud_count, 
                       ARRAY_AGG(transaction_id) as transactions
                FROM fraud_alerts
                WHERE detection_time >= NOW() - INTERVAL '30 minutes'
                  AND is_fraud = TRUE
                GROUP BY user_id
                HAVING COUNT(*) >= %s
            """
            cur.execute(query, (self.thresholds['rapid_frauds'],))
            
            rapid_sequences = cur.fetchall()
            
            for sequence in rapid_sequences:
                self.trigger_alert(
                    alert_type='RAPID_FRAUD_SEQUENCE',
                    severity='HIGH',
                    message=f"Rapid fraud sequence from user {sequence[0]}: {sequence[1]} frauds",
                    details={
                        'user_id': sequence[0],
                        'fraud_count': sequence[1],
                        'transaction_ids': sequence[2]
                    }
                )
            
            cur.close()
            conn.close()
            
            return len(rapid_sequences)
            
        except Exception as e:
            logger.error(f"Error checking rapid sequences: {e}")
            return 0
    
    def check_model_performance_degradation(self):
        """Check if model performance has degraded"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            # Get latest model performance
            query = """
                SELECT model_version, accuracy, precision_score, recall, f1_score
                FROM model_performance
                WHERE is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """
            cur.execute(query)
            result = cur.fetchone()
            
            if result:
                # Check if any metric is below threshold
                if result[1] < 0.85 or result[2] < 0.75 or result[3] < 0.75:
                    self.trigger_alert(
                        alert_type='MODEL_PERFORMANCE_DEGRADATION',
                        severity='MEDIUM',
                        message=f"Model {result[0]} performance below threshold",
                        details={
                            'model_version': result[0],
                            'accuracy': result[1],
                            'precision': result[2],
                            'recall': result[3],
                            'f1_score': result[4]
                        }
                    )
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error checking model performance: {e}")
    
    def check_system_health(self):
        """Check system health issues"""
        try:
            # Check Redis
            redis_healthy = self.redis_client.ping()
            if not redis_healthy:
                self.trigger_alert(
                    alert_type='SYSTEM_HEALTH',
                    severity='CRITICAL',
                    message='Redis connection failed',
                    details={'component': 'Redis'}
                )
            
            # Check PostgreSQL
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            
        except Exception as e:
            self.trigger_alert(
                alert_type='SYSTEM_HEALTH',
                severity='CRITICAL',
                message=f'System health check failed: {str(e)}',
                details={'error': str(e)}
            )
    
    def trigger_alert(self, alert_type, severity, message, details):
        """
        Trigger an alert
        
        Args:
            alert_type: Type of alert (HIGH_VALUE_FRAUD, FRAUD_RATE_SPIKE, etc.)
            severity: CRITICAL, HIGH, MEDIUM, LOW
            message: Alert message
            details: Additional details dict
        """
        alert = {
            'alert_type': alert_type,
            'severity': severity,
            'message': message,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Log alert
        logger.warning(f"[{severity}] {alert_type}: {message}")
        
        # Store in Redis for real-time access
        alert_key = f"alert:{alert_type}:{int(time.time())}"
        self.redis_client.setex(alert_key, 3600, json.dumps(alert))
        
        # Store in PostgreSQL audit log
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            query = """
                INSERT INTO audit_log (event_type, event_description, metadata)
                VALUES (%s, %s, %s)
            """
            cur.execute(query, (
                f'ALERT_{alert_type}',
                message,
                json.dumps(details)
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
        
        # Send notification (placeholder - would integrate with email/Slack/etc)
        self.send_notification(alert)
    
    def send_notification(self, alert):
        """
        Send notification via various channels
        This is a placeholder - integrate with actual notification services
        """
        # In production, integrate with:
        # - Email (SMTP)
        # - Slack webhook
        # - PagerDuty
        # - SMS (Twilio)
        
        logger.info(f"Notification sent for {alert['alert_type']}")
        
        # Example: Write to file for now
        try:
            with open('/tmp/fraud_alerts.log', 'a') as f:
                f.write(json.dumps(alert) + '\n')
        except Exception as e:
            logger.error(f"Error writing notification: {e}")
    
    def run_alert_monitoring(self, interval=60):
        """Run continuous alert monitoring"""
        logger.info(f"Starting alert monitoring (interval: {interval}s)")
        
        try:
            while True:
                logger.info("Running alert checks...")
                
                # Run all checks
                self.check_high_value_fraud()
                self.check_fraud_rate_spike()
                self.check_rapid_fraud_sequence()
                self.check_model_performance_degradation()
                self.check_system_health()
                
                logger.info(f"Alert checks complete. Next check in {interval}s")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Alert monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in alert monitoring: {e}")


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fraud Alert System')
    parser.add_argument('--postgres-host', default='localhost')
    parser.add_argument('--redis-host', default='localhost')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    
    args = parser.parse_args()
    
    conn_str = f"dbname=frauddb user=frauduser password=fraudpass host={args.postgres_host} port=5432"
    
    alert_system = AlertSystem(
        postgres_conn_str=conn_str,
        redis_host=args.redis_host
    )
    
    alert_system.run_alert_monitoring(interval=args.interval)


if __name__ == "__main__":
    main()