"""
Fraud Detection Model Training
Trains machine learning model on historical/synthetic transaction data
"""

import os
import sys
import json
import logging
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FraudModelTrainer:
    """Train and evaluate fraud detection models"""
    
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_names = []
        self.metrics = {}
        
    def generate_training_data(self, n_samples=50000, fraud_ratio=0.05):
        """
        Generate synthetic training data
        """
        logger.info(f"Generating {n_samples} training samples with {fraud_ratio*100}% fraud ratio")
        
        np.random.seed(42)
        n_fraud = int(n_samples * fraud_ratio)
        n_normal = n_samples - n_fraud

        # Normal transactions
        normal_amounts = np.random.lognormal(mean=4, sigma=1, size=n_normal)
        normal_hours = np.random.normal(loc=14, scale=4, size=n_normal) % 24
        normal_frequency = np.random.poisson(lam=5, size=n_normal)

        # Fraudulent transactions
        fraud_high_amounts = np.random.lognormal(mean=7, sigma=0.5, size=n_fraud // 2)
        fraud_low_amounts = np.random.uniform(0.01, 10, size=n_fraud // 2)
        fraud_amounts = np.concatenate([fraud_high_amounts, fraud_low_amounts])
        if len(fraud_amounts) < n_fraud:
            fraud_amounts = np.concatenate([fraud_amounts, np.random.uniform(0.01, 100, size=(n_fraud - len(fraud_amounts)))])

        fraud_hours_high = np.random.normal(loc=2, scale=2, size=n_fraud // 2) % 24
        fraud_hours_low = np.random.uniform(0, 24, size=n_fraud // 2)
        fraud_hours = np.concatenate([fraud_hours_high, fraud_hours_low])
        if len(fraud_hours) < n_fraud:
            fraud_hours = np.concatenate([fraud_hours, np.random.uniform(0, 24, size=(n_fraud - len(fraud_hours)))])

        fraud_frequency = np.random.poisson(lam=15, size=n_fraud)

        # Combine normal + fraud
        amounts = np.concatenate([normal_amounts, fraud_amounts])
        hours = np.concatenate([normal_hours, fraud_hours])
        frequencies = np.concatenate([normal_frequency, fraud_frequency])

        # Other categorical features
        merchants = np.random.choice(['Amazon', 'Walmart', 'Unknown', 'Foreign'], size=n_samples)
        countries = np.random.choice(['US', 'UK', 'RU', 'CN'], size=n_samples)
        transaction_types = np.random.choice(['purchase', 'withdrawal', 'transfer'], size=n_samples)
        day_of_week = np.random.randint(0, 7, size=n_samples)

        # Create DataFrame
        df = pd.DataFrame({
            'amount': amounts,
            'hour': hours,
            'day_of_week': day_of_week,
            'user_frequency': frequencies,
            'merchant': merchants,
            'country': countries,
            'transaction_type': transaction_types,
            'is_fraud': np.concatenate([np.zeros(n_normal), np.ones(n_fraud)])
        })

        # Derived features
        df['amount_log'] = np.log1p(df['amount'])
        df['is_night'] = ((df['hour'] >= 22) | (df['hour'] <= 6)).astype(int)
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_high_amount'] = (df['amount'] > df['amount'].quantile(0.9)).astype(int)
        df['is_unknown_merchant'] = (df['merchant'] == 'Unknown').astype(int)
        df['is_foreign_country'] = (df['country'].isin(['RU', 'CN'])).astype(int)

        logger.info(f"Generated dataset shape: {df.shape}")
        logger.info(f"Fraud distribution:\n{df['is_fraud'].value_counts()}")
        return df

    def preprocess_data(self, df):
        """Preprocess features for training"""
        X = df.drop('is_fraud', axis=1)
        y = df['is_fraud']

        categorical_cols = ['merchant', 'country', 'transaction_type']
        for col in categorical_cols:
            le = LabelEncoder()
            X[f'{col}_encoded'] = le.fit_transform(X[col])
            self.label_encoders[col] = le
            X = X.drop(col, axis=1)

        self.feature_names = X.columns.tolist()
        logger.info(f"Features: {self.feature_names}")

        X_scaled = self.scaler.fit_transform(X)
        return X_scaled, y

    def train_model(self, X_train, y_train):
        """Train the model"""
        logger.info(f"Training {self.model_type} model...")

        if self.model_type == 'logistic':
            self.model = LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced')
        elif self.model_type == 'random_forest':
            self.model = RandomForestClassifier(n_estimators=100, max_depth=10,
                                                random_state=42, class_weight='balanced', n_jobs=-1)
        elif self.model_type == 'gradient_boosting':
            self.model = GradientBoostingClassifier(n_estimators=100, max_depth=5,
                                                    learning_rate=0.1, random_state=42)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        self.model.fit(X_train, y_train)
        logger.info("Model training complete")

    def evaluate_model(self, X_test, y_test):
        """Evaluate model performance"""
        logger.info("Evaluating model...")
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]

        self.metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'f1_score': f1_score(y_test, y_pred),
            'roc_auc': roc_auc_score(y_test, y_pred_proba)
        }

        cm = confusion_matrix(y_test, y_pred)
        logger.info(f"Accuracy: {self.metrics['accuracy']:.4f}")
        logger.info(f"Precision: {self.metrics['precision']:.4f}")
        logger.info(f"Recall: {self.metrics['recall']:.4f}")
        logger.info(f"F1-Score: {self.metrics['f1_score']:.4f}")
        logger.info(f"ROC-AUC: {self.metrics['roc_auc']:.4f}")
        logger.info(f"Confusion Matrix:\n{cm}")

        if hasattr(self.model, 'feature_importances_'):
            feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
            sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            logger.info("Top 10 Important Features:")
            for feat, importance in sorted_features[:10]:
                logger.info(f"  {feat}: {importance:.4f}")
            self.metrics['feature_importance'] = feature_importance

        return self.metrics

    def save_model(self, model_dir='models/fraud_model_v1'):
        """Save trained model and artifacts"""
        os.makedirs(model_dir, exist_ok=True)
        os.makedirs(f"{model_dir}/data", exist_ok=True)
        os.makedirs(f"{model_dir}/metadata", exist_ok=True)

        joblib.dump(self.model, f"{model_dir}/data/model.pkl")
        joblib.dump(self.scaler, f"{model_dir}/data/scaler.pkl")
        joblib.dump(self.label_encoders, f"{model_dir}/data/label_encoders.pkl")

        metadata = {
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'metrics': self.metrics,
            'training_date': datetime.utcnow().isoformat(),
            'version': 'v1'
        }
        with open(f"{model_dir}/metadata/model_info.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model artifacts saved to {model_dir}")
        return model_dir


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Train Fraud Detection Model')
    parser.add_argument('--model-type', default='random_forest', choices=['logistic', 'random_forest', 'gradient_boosting'])
    parser.add_argument('--samples', type=int, default=50000)
    parser.add_argument('--fraud-ratio', type=float, default=0.05)
    parser.add_argument('--output-dir', default='models/fraud_model_v1')
    args = parser.parse_args()

    trainer = FraudModelTrainer(model_type=args.model_type)
    df = trainer.generate_training_data(n_samples=args.samples, fraud_ratio=args.fraud_ratio)
    X, y = trainer.preprocess_data(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    logger.info(f"Training set: {X_train.shape}, Test set: {X_test.shape}")
    trainer.train_model(X_train, y_train)
    trainer.evaluate_model(X_test, y_test)
    model_dir = trainer.save_model(model_dir=args.output_dir)

    logger.info("="*80)
    logger.info("Training Complete!")
    logger.info(f"Model saved to: {model_dir}")
    logger.info("="*80)


if __name__ == "__main__":
    main()
