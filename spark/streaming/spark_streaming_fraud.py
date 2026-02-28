"""
Spark Structured Streaming - Real-time Fraud Detection
Consumes transactions from Kafka, applies ML model, stores results
"""

import os
import sys
import json
import logging
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FraudDetectionStreaming:
    """Real-time fraud detection using Spark Structured Streaming"""
    
    def __init__(self, kafka_brokers='kafka:29092', kafka_topic='banking-transactions'):
        """Initialize Spark streaming application"""
        
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic
        
        # Initialize Spark Session
        self.spark = SparkSession.builder \
            .appName("FraudDetectionStreaming") \
            .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
            .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoint") \
            .getOrCreate()
        
        self.spark.sparkContext.setLogLevel("WARN")
        logger.info("Spark Session initialized")
        
        # Load ML model
        self.load_model()
    
    def load_model(self, model_path='/opt/models/fraud_model_v1'):
        """Load trained ML model and preprocessing artifacts"""
        try:
            self.model = joblib.load(f"{model_path}/data/model.pkl")
            self.scaler = joblib.load(f"{model_path}/data/scaler.pkl")
            self.label_encoders = joblib.load(f"{model_path}/data/label_encoders.pkl")
            
            # Load metadata
            with open(f"{model_path}/metadata/model_info.json", 'r') as f:
                self.model_metadata = json.load(f)
            
            self.feature_names = self.model_metadata['feature_names']
            self.model_version = self.model_metadata['version']
            
            logger.info(f"Model loaded: {self.model_version}")
            logger.info(f"Features: {self.feature_names}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            # Use a simple rule-based approach as fallback
            self.model = None
            logger.warning("Using rule-based fraud detection as fallback")
    
    def define_schema(self):
        """Define schema for incoming Kafka messages"""
        return StructType([
            StructField("transaction_id", StringType(), False),
            StructField("user_id", StringType(), False),
            StructField("amount", DoubleType(), False),
            StructField("currency", StringType(), True),
            StructField("merchant", StringType(), True),
            StructField("transaction_time", StringType(), False),
            StructField("country", StringType(), True),
            StructField("transaction_type", StringType(), True),
            StructField("is_fraud_actual", BooleanType(), True)
        ])
    
    def read_kafka_stream(self):
        """Read streaming data from Kafka"""
        logger.info(f"Reading from Kafka: {self.kafka_brokers}, topic: {self.kafka_topic}")
        
        df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.kafka_brokers) \
            .option("subscribe", self.kafka_topic) \
            .option("startingOffsets", "latest") \
            .load()
        
        # Parse JSON value
        schema = self.define_schema()
        
        parsed_df = df.select(
            from_json(col("value").cast("string"), schema).alias("data")
        ).select("data.*")
        
        logger.info("Kafka stream initialized")
        return parsed_df
    
    def feature_engineering(self, df):
        """Apply feature engineering to streaming data"""
        
        # Convert transaction_time to timestamp
        df = df.withColumn("transaction_timestamp", to_timestamp(col("transaction_time")))
        
        # Extract time features
        df = df.withColumn("hour", hour(col("transaction_timestamp")))
        df = df.withColumn("day_of_week", dayofweek(col("transaction_timestamp")))
        
        # Derived features
        df = df.withColumn("amount_log", log1p(col("amount")))
        df = df.withColumn("is_night", 
                          when((col("hour") >= 22) | (col("hour") <= 6), 1).otherwise(0))
        df = df.withColumn("is_weekend", 
                          when(col("day_of_week").isin([1, 7]), 1).otherwise(0))
        
        # Simulated user frequency (in production, would query from database)
        df = df.withColumn("user_frequency", lit(15))  # Placeholder
        
        # High amount flag
        df = df.withColumn("is_high_amount", 
                          when(col("amount") > 1000, 1).otherwise(0))
        
        # Unknown merchant flag
        df = df.withColumn("is_unknown_merchant",
                          when(col("merchant").isin(["Unknown Merchant", "Suspicious Shop", "Foreign Vendor"]), 1).otherwise(0))
        
        # Foreign country flag
        df = df.withColumn("is_foreign_country",
                          when(col("country").isin(["RU", "CN"]), 1).otherwise(0))
        
        return df
    
    def apply_fraud_detection(self, batch_df, batch_id):
        """
        Apply fraud detection model to each batch
        This is a UDF applied to micro-batches
        """
        try:
            logger.info(f"Processing batch {batch_id} with {batch_df.count()} records")
            
            if batch_df.isEmpty():
                return
            
            # Convert to Pandas for ML prediction
            pandas_df = batch_df.toPandas()
            
            if self.model is not None:
                # Prepare features for model
                feature_cols = ['amount', 'hour', 'day_of_week', 'user_frequency', 
                              'amount_log', 'is_night', 'is_weekend', 'is_high_amount',
                              'is_unknown_merchant', 'is_foreign_country']
                
                # Add encoded categorical features
                for col_name in ['merchant', 'country', 'transaction_type']:
                    if col_name in pandas_df.columns and col_name in self.label_encoders:
                        le = self.label_encoders[col_name]
                        # Handle unknown categories
                        pandas_df[f'{col_name}_encoded'] = pandas_df[col_name].apply(
                            lambda x: le.transform([x])[0] if x in le.classes_ else -1
                        )
                        feature_cols.append(f'{col_name}_encoded')
                
                # Ensure all features exist
                for feat in self.feature_names:
                    if feat not in pandas_df.columns:
                        pandas_df[feat] = 0
                
                # Get features in correct order
                X = pandas_df[self.feature_names]
                
                # Scale features
                X_scaled = self.scaler.transform(X)
                
                # Predict
                fraud_predictions = self.model.predict(X_scaled)
                fraud_scores = self.model.predict_proba(X_scaled)[:, 1]
                logger.info(f"Scores sample: {fraud_scores[:5]}, Predictions: {fraud_predictions[:5]}")
                
                pandas_df["is_fraud"] = fraud_predictions.astype(bool)
                pandas_df['fraud_score'] = fraud_scores
            else:
                # Rule-based fallback
                pandas_df['fraud_score'] = pandas_df.apply(self.rule_based_score, axis=1)
                pandas_df['is_fraud'] = pandas_df['fraud_score'] > 0.7
            
            pandas_df['model_version'] = self.model_version if self.model else 'rule_based'
            pandas_df['detection_time'] = datetime.utcnow()
            
            # Store transactions in PostgreSQL
            self.store_transactions(pandas_df)
            
            # Store fraud alerts
            fraud_alerts = pandas_df[pandas_df['is_fraud'] == True]
            if not fraud_alerts.empty:
                self.store_fraud_alerts(fraud_alerts)
                self.cache_in_redis(fraud_alerts)
            
            logger.info(f"Batch {batch_id} processed: {len(fraud_alerts)} frauds detected")
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {e}")
    
    def rule_based_score(self, row):
        """Simple rule-based fraud scoring as fallback"""
        score = 0.0
        
        # High amount
        if row['amount'] > 1000:
            score += 0.3
        
        # Night transaction
        if row['is_night'] == 1:
            score += 0.2
        
        # Unknown merchant
        if row['is_unknown_merchant'] == 1:
            score += 0.3
        
        # Foreign country
        if row['is_foreign_country'] == 1:
            score += 0.2
        
        return min(score, 1.0)
    
    def store_transactions(self, df):
        """Store all transactions in PostgreSQL"""
        try:
            from sqlalchemy import create_engine
            
            engine = create_engine('postgresql://frauduser:fraudpass@postgres:5432/frauddb')
            
            # Select relevant columns
            cols = ['transaction_id', 'user_id', 'amount', 'currency', 'merchant',
                   'transaction_time', 'country', 'transaction_type']
            
            df[cols].to_sql('transactions', engine, if_exists='append', index=False)
            logger.info(f"Stored {len(df)} transactions in PostgreSQL")
        except Exception as e:
            logger.error(f"Error storing transactions: {e}")
    
    def store_fraud_alerts(self, df):
        """Store fraud alerts in PostgreSQL"""
        try:
            from sqlalchemy import create_engine
            
            engine = create_engine('postgresql://frauduser:fraudpass@postgres:5432/frauddb')
            
            # Prepare alert data
            alert_data = df[['transaction_id', 'user_id', 'amount', 'merchant',
                           'fraud_score', 'is_fraud', 'model_version', 'transaction_time']].copy()
            alert_data['alert_status'] = 'pending'
            
            alert_data.to_sql('fraud_alerts', engine, if_exists='append', index=False)
            logger.info(f"Stored {len(df)} fraud alerts in PostgreSQL")
        except Exception as e:
            logger.error(f"Error storing fraud alerts: {e}")
    
    def cache_in_redis(self, df):
        """Cache recent fraud alerts in Redis"""
        try:
            import redis
            
            r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
            
            for _, row in df.iterrows():
                alert = {
                    'transaction_id': row['transaction_id'],
                    'user_id': row['user_id'],
                    'amount': float(row['amount']),
                    'fraud_score': float(row['fraud_score']),
                    'timestamp': str(row.get('detection_time', datetime.utcnow()))
                }
                
                # Store with expiration (1 hour)
                r.setex(
                    f"fraud_alert:{row['transaction_id']}",
                    3600,
                    json.dumps(alert)
                )
            
            logger.info(f"Cached {len(df)} alerts in Redis")
        except Exception as e:
            logger.error(f"Error caching in Redis: {e}")
    

    def start_streaming(self):
        """Start the streaming application"""
        logger.info("Starting fraud detection streaming...")
        
        # Read stream
        transaction_stream = self.read_kafka_stream()
        
        # Apply feature engineering
        enriched_stream = self.feature_engineering(transaction_stream)
        
        # Process each batch with ML model
        query = enriched_stream.writeStream \
            .foreachBatch(self.apply_fraud_detection) \
            .outputMode("append") \
            .start()
        
        logger.info("Streaming query started")
        
        # Wait for termination
        query.awaitTermination()


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fraud Detection Streaming')
    parser.add_argument('--kafka-brokers', default='kafka:29092')
    parser.add_argument('--kafka-topic', default='banking-transactions')
    parser.add_argument('--model-path', default='/opt/models/fraud_model_')
    
    args = parser.parse_args()
    
    detector = FraudDetectionStreaming(
        kafka_brokers=args.kafka_brokers,
        kafka_topic=args.kafka_topic
    )
    
    detector.start_streaming()


if __name__ == "__main__":
    main()