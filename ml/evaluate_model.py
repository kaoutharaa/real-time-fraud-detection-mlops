"""
Model Evaluation Script
Evaluates trained fraud detection model on test data
"""

import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score, roc_curve
)
import matplotlib
matplotlib.use('Agg')  # Headless mode for servers
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelEvaluator:
    """Evaluate fraud detection model"""

    def __init__(self, model_dir):
        """Load model and artifacts"""
        self.model_dir = model_dir
        self.load_model()

    def load_model(self):
        """Load trained model, scaler, and encoders"""
        logger.info(f"Loading model from {self.model_dir}")

        self.model = joblib.load(f"{self.model_dir}/data/model.pkl")
        self.scaler = joblib.load(f"{self.model_dir}/data/scaler.pkl")
        self.label_encoders = joblib.load(f"{self.model_dir}/data/label_encoders.pkl")

        with open(f"{self.model_dir}/metadata/model_info.json", 'r') as f:
            self.metadata = json.load(f)

        self.feature_names = self.metadata['feature_names']
        logger.info(f"Model loaded: {self.metadata.get('version', 'v1')}")

    def generate_test_data(self, n_samples=10000):
        """Generate synthetic test dataset"""
        logger.info(f"Generating test dataset with {n_samples} samples")

        np.random.seed(123)  # Different seed than training

        fraud_ratio = 0.05
        n_fraud = int(n_samples * fraud_ratio)
        n_normal = n_samples - n_fraud

        # Normal transactions
        normal_amounts = np.random.lognormal(mean=4, sigma=1, size=n_normal)
        normal_hours = np.random.normal(loc=14, scale=4, size=n_normal) % 24
        normal_frequency = np.random.poisson(lam=5, size=n_normal)

        # Fraudulent transactions
        fraud_high_amounts = np.random.lognormal(mean=7, sigma=0.5, size=n_fraud // 2)
        fraud_low_amounts = np.random.uniform(0.01, 10, size=n_fraud - len(fraud_high_amounts))
        fraud_amounts = np.concatenate([fraud_high_amounts, fraud_low_amounts])

        fraud_hours_high = np.random.normal(loc=2, scale=2, size=n_fraud // 2) % 24
        fraud_hours_low = np.random.uniform(0, 24, size=n_fraud - len(fraud_hours_high))
        fraud_hours = np.concatenate([fraud_hours_high, fraud_hours_low])

        fraud_frequency = np.random.poisson(lam=15, size=n_fraud)

        # Combine normal + fraud
        amounts = np.concatenate([normal_amounts, fraud_amounts])
        hours = np.concatenate([normal_hours, fraud_hours])
        frequencies = np.concatenate([normal_frequency, fraud_frequency])

        # Categorical features
        merchants = np.random.choice(['Amazon', 'Walmart', 'Unknown', 'Foreign'], size=n_samples)
        countries = np.random.choice(['US', 'UK', 'RU', 'CN'], size=n_samples)
        transaction_types = np.random.choice(['purchase', 'withdrawal', 'transfer'], size=n_samples)
        day_of_week = np.random.randint(0, 7, size=n_samples)

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

        return df

    def preprocess_data(self, df):
        """Preprocess test data"""
        X = df.drop('is_fraud', axis=1)
        y = df['is_fraud']

        categorical_cols = ['merchant', 'country', 'transaction_type']
        for col in categorical_cols:
            if col in X.columns and col in self.label_encoders:
                le = self.label_encoders[col]
                X[f'{col}_encoded'] = X[col].apply(
                    lambda x: le.transform([x])[0] if x in le.classes_ else -1
                )
                X = X.drop(col, axis=1)

        # Ensure all features exist in correct order
        for feat in self.feature_names:
            if feat not in X.columns:
                X[feat] = 0

        X = X[self.feature_names]
        X_scaled = self.scaler.transform(X)
        return X_scaled, y

    def evaluate(self, X_test, y_test):
        """Evaluate model performance"""
        logger.info("Evaluating model...")

        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]

        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'f1_score': f1_score(y_test, y_pred),
            'roc_auc': roc_auc_score(y_test, y_pred_proba)
        }

        logger.info("=" * 60)
        logger.info("EVALUATION RESULTS")
        logger.info("=" * 60)
        logger.info(f"Accuracy:  {metrics['accuracy']:.4f}")
        logger.info(f"Precision: {metrics['precision']:.4f}")
        logger.info(f"Recall:    {metrics['recall']:.4f}")
        logger.info(f"F1-Score:  {metrics['f1_score']:.4f}")
        logger.info(f"ROC-AUC:   {metrics['roc_auc']:.4f}")

        cm = confusion_matrix(y_test, y_pred)
        logger.info("\nConfusion Matrix:")
        logger.info(f"                Predicted")
        logger.info(f"              Normal  Fraud")
        logger.info(f"Actual Normal  {cm[0][0]:5d}  {cm[0][1]:5d}")
        logger.info(f"       Fraud   {cm[1][0]:5d}  {cm[1][1]:5d}")

        logger.info("\nDetailed Classification Report:")
        logger.info(classification_report(y_test, y_pred, target_names=['Normal', 'Fraud']))

        return metrics, cm, y_pred_proba

    def plot_results(self, y_test, y_pred_proba, cm):
        """Generate evaluation plots"""
        logger.info("Generating plots...")

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # ROC Curve
        fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
        auc = roc_auc_score(y_test, y_pred_proba)

        axes[0].plot(fpr, tpr, label=f'ROC Curve (AUC = {auc:.3f})')
        axes[0].plot([0, 1], [0, 1], 'k--', label='Random')
        axes[0].set_xlabel('False Positive Rate')
        axes[0].set_ylabel('True Positive Rate')
        axes[0].set_title('ROC Curve')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # Confusion Matrix
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[1])
        axes[1].set_xlabel('Predicted')
        axes[1].set_ylabel('Actual')
        axes[1].set_title('Confusion Matrix')
        axes[1].set_xticklabels(['Normal', 'Fraud'])
        axes[1].set_yticklabels(['Normal', 'Fraud'])

        plt.tight_layout()
        plot_path = f"{self.model_dir}/evaluation_results.png"
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        logger.info(f"Plots saved to {plot_path}")
        plt.close()

    def save_evaluation_report(self, metrics):
        """Save evaluation report to JSON"""
        report_path = f"{self.model_dir}/evaluation_report.json"

        report = {
            'model_version': self.metadata.get('version', 'v1'),
            'evaluation_date': pd.Timestamp.now().isoformat(),
            'metrics': metrics
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Evaluation report saved to {report_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Evaluate Fraud Detection Model')
    parser.add_argument('--model-dir', default='models/fraud_model_latest', help='Model directory')
    parser.add_argument('--test-samples', type=int, default=10000, help='Number of test samples')

    args = parser.parse_args()

    evaluator = ModelEvaluator(args.model_dir)

    # Generate test data
    df_test = evaluator.generate_test_data(n_samples=args.test_samples)

    # Preprocess
    X_test, y_test = evaluator.preprocess_data(df_test)

    # Evaluate
    metrics, cm, y_pred_proba = evaluator.evaluate(X_test, y_test)

    # Plot results
    evaluator.plot_results(y_test, y_pred_proba, cm)

    # Save report
    evaluator.save_evaluation_report(metrics)

    logger.info("=" * 60)
    logger.info("Evaluation Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
