"""
Monitoring Metrics Collector
Collects and reports system and ML performance metrics
"""

import time
import logging
from datetime import datetime
import psycopg2
import redis
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collect and store system metrics"""
    
    def __init__(self, postgres_conn_str=None, redis_host='localhost'):
        """Initialize metrics collector"""
        self.postgres_conn_str = postgres_conn_str or \
            "dbname=frauddb user=frauduser password=fraudpass host=localhost port=5432"
        
        self.redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
        
        logger.info("Metrics collector initialized")
    
    def get_postgres_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(self.postgres_conn_str)
    
    def collect_transaction_metrics(self):
        """Collect transaction-related metrics"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            # Transactions per minute
            query = """
                SELECT COUNT(*) as tx_count
                FROM transactions
                WHERE created_at >= NOW() - INTERVAL '1 minute'
            """
            cur.execute(query)
            tx_per_minute = cur.fetchone()[0]
            
            # Total transactions today
            query = """
                SELECT COUNT(*) as tx_count
                FROM transactions
                WHERE DATE(created_at) = CURRENT_DATE
            """
            cur.execute(query)
            tx_today = cur.fetchone()[0]
            
            # Average transaction amount
            query = """
                SELECT AVG(amount) as avg_amount
                FROM transactions
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """
            cur.execute(query)
            avg_amount = cur.fetchone()[0] or 0
            
            metrics = {
                'transactions_per_minute': tx_per_minute,
                'transactions_today': tx_today,
                'avg_amount_1h': float(avg_amount)
            }
            
            cur.close()
            conn.close()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting transaction metrics: {e}")
            return {}
    
    def collect_fraud_metrics(self):
        """Collect fraud detection metrics"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            # Fraud alerts in last hour
            query = """
                SELECT COUNT(*) as fraud_count
                FROM fraud_alerts
                WHERE detection_time >= NOW() - INTERVAL '1 hour'
            """
            cur.execute(query)
            frauds_1h = cur.fetchone()[0]
            
            # Fraud rate
            query = """
                WITH recent_data AS (
                    SELECT COUNT(DISTINCT t.transaction_id) as total_tx,
                           COUNT(DISTINCT f.transaction_id) as fraud_tx
                    FROM transactions t
                    LEFT JOIN fraud_alerts f ON t.transaction_id = f.transaction_id
                    WHERE t.created_at >= NOW() - INTERVAL '1 hour'
                )
                SELECT 
                    CASE WHEN total_tx > 0 
                         THEN CAST(fraud_tx AS FLOAT) / total_tx 
                         ELSE 0 
                    END as fraud_rate
                FROM recent_data
            """
            cur.execute(query)
            fraud_rate = cur.fetchone()[0] or 0
            
            # Average fraud score
            query = """
                SELECT AVG(fraud_score) as avg_fraud_score
                FROM fraud_alerts
                WHERE detection_time >= NOW() - INTERVAL '1 hour'
            """
            cur.execute(query)
            avg_fraud_score = cur.fetchone()[0] or 0
            
            # Pending alerts
            query = """
                SELECT COUNT(*) as pending_alerts
                FROM fraud_alerts
                WHERE alert_status = 'pending'
            """
            cur.execute(query)
            pending_alerts = cur.fetchone()[0]
            
            metrics = {
                'frauds_detected_1h': frauds_1h,
                'fraud_rate': float(fraud_rate),
                'avg_fraud_score': float(avg_fraud_score),
                'pending_alerts': pending_alerts
            }
            
            cur.close()
            conn.close()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting fraud metrics: {e}")
            return {}
    
    def collect_model_performance(self):
        """Collect ML model performance metrics"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            # Get active model metrics
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
                metrics = {
                    'model_version': result[0],
                    'accuracy': float(result[1]) if result[1] else 0,
                    'precision': float(result[2]) if result[2] else 0,
                    'recall': float(result[3]) if result[3] else 0,
                    'f1_score': float(result[4]) if result[4] else 0
                }
            else:
                metrics = {}
            
            cur.close()
            conn.close()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting model performance: {e}")
            return {}
    
    def collect_system_health(self):
        """Collect system health metrics"""
        try:
            # Redis health
            redis_healthy = self.redis_client.ping()
            
            # PostgreSQL health
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            postgres_healthy = cur.fetchone()[0] == 1
            cur.close()
            conn.close()
            
            # Redis cache size
            cache_size = self.redis_client.dbsize()
            
            metrics = {
                'redis_healthy': redis_healthy,
                'postgres_healthy': postgres_healthy,
                'redis_cache_size': cache_size
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system health: {e}")
            return {
                'redis_healthy': False,
                'postgres_healthy': False,
                'redis_cache_size': 0
            }
    
    def store_metrics(self, metrics_dict):
        """Store metrics in database"""
        try:
            conn = self.get_postgres_connection()
            cur = conn.cursor()
            
            for metric_name, metric_value in metrics_dict.items():
                # Determine metric type
                if isinstance(metric_value, (int, float)):
                    value = float(metric_value)
                    unit = 'count' if isinstance(metric_value, int) else 'ratio'
                elif isinstance(metric_value, bool):
                    value = 1.0 if metric_value else 0.0
                    unit = 'boolean'
                else:
                    continue
                
                query = """
                    INSERT INTO monitoring_metrics (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                """
                cur.execute(query, (metric_name, value, unit))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Stored {len(metrics_dict)} metrics")
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    def collect_all_metrics(self):
        """Collect all metrics"""
        logger.info("Collecting all metrics...")
        
        all_metrics = {}
        
        # Transaction metrics
        tx_metrics = self.collect_transaction_metrics()
        all_metrics.update(tx_metrics)
        logger.info(f"Transaction metrics: {tx_metrics}")
        
        # Fraud metrics
        fraud_metrics = self.collect_fraud_metrics()
        all_metrics.update(fraud_metrics)
        logger.info(f"Fraud metrics: {fraud_metrics}")
        
        # Model performance
        model_metrics = self.collect_model_performance()
        all_metrics.update(model_metrics)
        logger.info(f"Model metrics: {model_metrics}")
        
        # System health
        health_metrics = self.collect_system_health()
        all_metrics.update(health_metrics)
        logger.info(f"Health metrics: {health_metrics}")
        
        # Store metrics
        self.store_metrics(all_metrics)
        
        # Also cache latest metrics in Redis
        self.redis_client.setex(
            'latest_metrics',
            300,  # 5 minutes TTL
            json.dumps(all_metrics, default=str)
        )
        
        return all_metrics
    
    def run_continuous_monitoring(self, interval=60):
        """Run continuous monitoring loop"""
        logger.info(f"Starting continuous monitoring (interval: {interval}s)")
        
        try:
            while True:
                self.collect_all_metrics()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Metrics Collector')
    parser.add_argument('--postgres-host', default='localhost')
    parser.add_argument('--redis-host', default='localhost')
    parser.add_argument('--interval', type=int, default=60, help='Collection interval in seconds')
    parser.add_argument('--once', action='store_true', help='Collect metrics once and exit')
    
    args = parser.parse_args()
    
    conn_str = f"dbname=frauddb user=frauduser password=fraudpass host={args.postgres_host} port=5432"
    
    collector = MetricsCollector(
        postgres_conn_str=conn_str,
        redis_host=args.redis_host
    )
    
    if args.once:
        metrics = collector.collect_all_metrics()
        print(json.dumps(metrics, indent=2))
    else:
        collector.run_continuous_monitoring(interval=args.interval)


if __name__ == "__main__":
    main()