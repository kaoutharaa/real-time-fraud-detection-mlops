"""
Batch Feature Engineering for Historical Data
Prepares historical transaction data for model training
"""

import logging
from datetime import datetime, timedelta
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchFeatureEngineer:
    """Batch processing for feature engineering"""
    
    def __init__(self):
        """Initialize Spark Session for batch processing"""
        self.spark = SparkSession.builder \
            .appName("BatchFeatureEngineering") \
            .config("spark.driver.memory", "4g") \
            .getOrCreate()
        
        self.spark.sparkContext.setLogLevel("WARN")
        logger.info("Spark Session initialized for batch processing")
    
    def load_historical_data(self, path='/opt/data/historical_transactions.csv'):
        """Load historical transaction data"""
        logger.info(f"Loading historical data from {path}")
        
        schema = StructType([
            StructField("transaction_id", StringType(), False),
            StructField("user_id", StringType(), False),
            StructField("amount", DoubleType(), False),
            StructField("currency", StringType(), True),
            StructField("merchant", StringType(), True),
            StructField("transaction_time", TimestampType(), False),
            StructField("country", StringType(), True),
            StructField("transaction_type", StringType(), True),
            StructField("is_fraud", IntegerType(), True)
        ])
        
        df = self.spark.read.csv(path, header=True, schema=schema)
        logger.info(f"Loaded {df.count()} historical transactions")
        
        return df
    
    def create_time_features(self, df):
        """Create time-based features"""
        logger.info("Creating time-based features")
        
        df = df.withColumn("hour", hour(col("transaction_time")))
        df = df.withColumn("day_of_week", dayofweek(col("transaction_time")))
        df = df.withColumn("day_of_month", dayofmonth(col("transaction_time")))
        df = df.withColumn("month", month(col("transaction_time")))
        
        # Derived time features
        df = df.withColumn("is_night", 
                          when((col("hour") >= 22) | (col("hour") <= 6), 1).otherwise(0))
        df = df.withColumn("is_weekend", 
                          when(col("day_of_week").isin([1, 7]), 1).otherwise(0))
        df = df.withColumn("is_business_hours",
                          when((col("hour") >= 9) & (col("hour") <= 17), 1).otherwise(0))
        
        return df
    
    def create_amount_features(self, df):
        """Create amount-based features"""
        logger.info("Creating amount-based features")
        
        # Log transformation
        df = df.withColumn("amount_log", log1p(col("amount")))
        
        # Amount categories
        df = df.withColumn("is_high_amount",
                          when(col("amount") > 1000, 1).otherwise(0))
        df = df.withColumn("is_micro_transaction",
                          when(col("amount") < 10, 1).otherwise(0))
        
        # Amount percentile (approximate)
        df = df.withColumn("amount_percentile",
                          percent_rank().over(Window.orderBy("amount")))
        
        return df
    
    def create_user_features(self, df):
        """Create user behavioral features"""
        logger.info("Creating user behavioral features")
        
        # Window for user-level aggregations
        user_window = Window.partitionBy("user_id")
        user_time_window = Window.partitionBy("user_id").orderBy("transaction_time") \
                                .rangeBetween(-86400 * 7, 0)  # 7 days lookback
        
        # User transaction frequency
        df = df.withColumn("user_tx_count", count("*").over(user_window))
        df = df.withColumn("user_tx_count_7d", count("*").over(user_time_window))
        
        # User average amount
        df = df.withColumn("user_avg_amount", avg("amount").over(user_window))
        df = df.withColumn("user_avg_amount_7d", avg("amount").over(user_time_window))
        
        # Deviation from user's typical behavior
        df = df.withColumn("amount_deviation_from_avg",
                          (col("amount") - col("user_avg_amount")) / (col("user_avg_amount") + 1))
        
        # Time since last transaction
        df = df.withColumn("prev_transaction_time",
                          lag("transaction_time").over(Window.partitionBy("user_id").orderBy("transaction_time")))
        df = df.withColumn("hours_since_last_tx",
                          (unix_timestamp("transaction_time") - unix_timestamp("prev_transaction_time")) / 3600)
        df = df.withColumn("hours_since_last_tx", 
                          coalesce(col("hours_since_last_tx"), lit(24)))
        
        return df
    
    def create_merchant_features(self, df):
        """Create merchant-based features"""
        logger.info("Creating merchant-based features")
        
        # Merchant risk indicators
        df = df.withColumn("is_unknown_merchant",
                          when(col("merchant").isin(["Unknown Merchant", "Suspicious Shop", "Foreign Vendor"]), 1).otherwise(0))
        
        # Merchant transaction count
        merchant_window = Window.partitionBy("merchant")
        df = df.withColumn("merchant_tx_count", count("*").over(merchant_window))
        df = df.withColumn("merchant_avg_amount", avg("amount").over(merchant_window))
        
        return df
    
    def create_location_features(self, df):
        """Create location-based features"""
        logger.info("Creating location-based features")
        
        # High-risk countries
        df = df.withColumn("is_high_risk_country",
                          when(col("country").isin(["RU", "CN", "NG", "PK"]), 1).otherwise(0))
        
        # Domestic vs international
        df = df.withColumn("is_domestic",
                          when(col("country") == "US", 1).otherwise(0))
        
        return df
    
    def create_velocity_features(self, df):
        """Create velocity-based features (rapid successive transactions)"""
        logger.info("Creating velocity features")
        
        # Transactions in last hour per user
        velocity_window = Window.partitionBy("user_id").orderBy("transaction_time") \
                               .rangeBetween(-3600, 0)
        
        df = df.withColumn("tx_count_1h", count("*").over(velocity_window))
        df = df.withColumn("total_amount_1h", sum("amount").over(velocity_window))
        
        # High velocity indicator
        df = df.withColumn("is_high_velocity",
                          when(col("tx_count_1h") > 5, 1).otherwise(0))
        
        return df
    
    def engineer_all_features(self, df):
        """Apply all feature engineering steps"""
        logger.info("Starting comprehensive feature engineering")
        
        df = self.create_time_features(df)
        df = self.create_amount_features(df)
        df = self.create_user_features(df)
        df = self.create_merchant_features(df)
        df = self.create_location_features(df)
        df = self.create_velocity_features(df)
        
        logger.info("Feature engineering complete")
        return df
    
    def save_features(self, df, output_path='/opt/data/features'):
        """Save engineered features"""
        logger.info(f"Saving features to {output_path}")
        
        df.write.mode("overwrite").parquet(output_path)
        
        logger.info(f"Features saved to {output_path}")
    
    def generate_feature_summary(self, df):
        """Generate summary statistics of features"""
        logger.info("Generating feature summary")
        
        # Select numeric columns
        numeric_cols = [field.name for field in df.schema.fields 
                       if isinstance(field.dataType, (IntegerType, DoubleType, LongType))]
        
        summary = df.select(numeric_cols).summary()
        summary.show()
        
        # Fraud distribution
        logger.info("Fraud distribution:")
        df.groupBy("is_fraud").count().show()
        
        return summary


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch Feature Engineering')
    parser.add_argument('--input', default='/opt/data/historical_transactions.csv')
    parser.add_argument('--output', default='/opt/data/features')
    
    args = parser.parse_args()
    
    engineer = BatchFeatureEngineer()
    
    # Load data
    df = engineer.load_historical_data(args.input)
    
    # Engineer features
    df_features = engineer.engineer_all_features(df)
    
    # Show sample
    logger.info("Sample of engineered features:")
    df_features.select("transaction_id", "amount", "is_fraud", "fraud_score_rule").show(10)
    
    # Generate summary
    engineer.generate_feature_summary(df_features)
    
    # Save
    engineer.save_features(df_features, args.output)
    
    logger.info("Batch feature engineering complete!")


if __name__ == "__main__":
    main()