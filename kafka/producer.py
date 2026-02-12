"""
Kafka Producer for Banking Transactions
Simulates real-time banking transactions and publishes to Kafka
"""

import json
import time
import random
from datetime import datetime
from kafka import KafkaProducer
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TransactionProducer:
    def __init__(self, bootstrap_servers='localhost:9092', topic='banking-transactions'):
        """Initialize Kafka producer"""
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        logger.info(f"Kafka Producer initialized for topic: {topic}")

    def generate_transaction(self, fraud_probability=0.05):
        """Generate a random banking transaction"""
        
        # User IDs pool
        user_ids = [f"USER_{i:04d}" for i in range(1, 1001)]
        
        # Merchants
        merchants = [
            "Amazon", "Walmart", "Target", "Apple Store", "Best Buy",
            "Starbucks", "McDonald's", "Shell Gas", "Uber", "Netflix",
            "Steam Games", "PlayStation Store", "Microsoft", "Google Play",
            "Unknown Merchant", "Suspicious Shop", "Foreign Vendor"
        ]
        
        # Determine if this is a fraudulent transaction
        is_fraud = random.random() < fraud_probability
        
        # Generate transaction details
        user_id = random.choice(user_ids)
        merchant = random.choice(merchants)
        
        if is_fraud:
            # Fraudulent transactions tend to have unusual patterns
            amount = random.choice([
                round(random.uniform(1000, 5000), 2),  # High amounts
                round(random.uniform(0.01, 10), 2),    # Very low amounts (testing)
                round(random.uniform(500, 2000), 2)
            ])
            # More likely to be at unusual times or unknown merchants
            if random.random() > 0.5:
                merchant = random.choice(["Unknown Merchant", "Suspicious Shop", "Foreign Vendor"])
        else:
            # Normal transactions
            amount = round(random.uniform(5, 500), 2)
        
        transaction = {
            "transaction_id": f"TXN_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
            "user_id": user_id,
            "amount": amount,
            "currency": random.choice(["USD", "EUR", "GBP"]),
            "merchant": merchant,
            "transaction_time": datetime.utcnow().isoformat(),
            "country": random.choice(["US", "UK", "FR", "DE", "CN", "RU"]),
            "transaction_type": random.choice(["purchase", "withdrawal", "transfer", "payment"]),
            # Hidden label for validation (not used in real-time detection)
            "is_fraud_actual": is_fraud
        }
        
        return transaction

    def produce_transactions(self, num_transactions=None, delay=1.0):
        """
        Produce transactions to Kafka
        
        Args:
            num_transactions: Number of transactions to produce (None for infinite)
            delay: Delay between transactions in seconds
        """
        count = 0
        try:
            while num_transactions is None or count < num_transactions:
                transaction = self.generate_transaction()
                
                # Send to Kafka
                self.producer.send(
                    self.topic,
                    key=transaction['transaction_id'],
                    value=transaction
                )
                
                count += 1
                logger.info(f"Sent transaction {count}: {transaction['transaction_id']} "
                          f"- Amount: ${transaction['amount']} "
                          f"- Merchant: {transaction['merchant']} "
                          f"- Fraud: {transaction['is_fraud_actual']}")
                
                time.sleep(delay)
                
        except KeyboardInterrupt:
            logger.info("Producer stopped by user")
        except Exception as e:
            logger.error(f"Error producing transaction: {e}")
        finally:
            self.producer.flush()
            self.producer.close()
            logger.info(f"Producer closed. Total transactions sent: {count}")


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kafka Transaction Producer')
    parser.add_argument('--broker', default='localhost:9092', help='Kafka broker address')
    parser.add_argument('--topic', default='banking-transactions', help='Kafka topic')
    parser.add_argument('--num', type=int, default=None, help='Number of transactions (default: infinite)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between transactions in seconds')
    parser.add_argument('--fraud-rate', type=float, default=0.05, help='Fraud probability (0.0-1.0)')
    
    args = parser.parse_args()
    
    producer = TransactionProducer(bootstrap_servers=args.broker, topic=args.topic)
    
    logger.info(f"Starting transaction producer...")
    logger.info(f"Fraud rate: {args.fraud_rate * 100}%")
    logger.info(f"Delay: {args.delay}s")
    
    # Override fraud probability in generate_transaction
    original_generate = producer.generate_transaction
    producer.generate_transaction = lambda: original_generate(fraud_probability=args.fraud_rate)
    
    producer.produce_transactions(num_transactions=args.num, delay=args.delay)


if __name__ == "__main__":
    main()