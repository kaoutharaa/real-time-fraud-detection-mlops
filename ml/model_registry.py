"""
Model Registry
Manages model versions and metadata in the database
"""

import os
import sys
import json
import logging
from datetime import datetime
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelRegistry:
    """Manage ML model versions"""
    
    def __init__(self, db_conn_str=None):
        """Initialize registry"""
        self.db_conn_str = db_conn_str or \
            "dbname=frauddb user=frauduser password=fraudpass host=localhost port=5432"
    
    def register_model(self, model_dir):
        """Register a new model version"""
        logger.info(f"Registering model from {model_dir}")
        
        # Load model metadata
        metadata_path = f"{model_dir}/metadata/model_info.json"
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        conn = psycopg2.connect(self.db_conn_str)
        cur = conn.cursor()
        
        # Insert model performance
        query = """
            INSERT INTO model_performance (
                model_version, accuracy, precision_score, recall, f1_score,
                training_date, feature_importance, hyperparameters, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        metrics = metadata.get('metrics', {})
        
        cur.execute(query, (
            metadata['version'],
            metrics.get('accuracy'),
            metrics.get('precision'),
            metrics.get('recall'),
            metrics.get('f1_score'),
            metadata.get('training_date'),
            json.dumps(metrics.get('feature_importance', {})),
            json.dumps({'model_type': metadata.get('model_type')}),
            False  # Not active by default
        ))
        
        model_id = cur.fetchone()[0]
        conn.commit()
        
        logger.info(f"Model registered with ID: {model_id}")
        
        # Log to audit
        audit_query = """
            INSERT INTO audit_log (event_type, event_description, model_version, metadata)
            VALUES (%s, %s, %s, %s)
        """
        cur.execute(audit_query, (
            'MODEL_REGISTERED',
            f"New model version registered: {metadata['version']}",
            metadata['version'],
            json.dumps(metadata)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Model {metadata['version']} registered successfully")
    
    def activate_model(self, model_version):
        """Activate a model version (deactivates others)"""
        logger.info(f"Activating model: {model_version}")
        
        conn = psycopg2.connect(self.db_conn_str)
        cur = conn.cursor()
        
        # Deactivate all models
        cur.execute("UPDATE model_performance SET is_active = FALSE")
        
        # Activate specific version
        cur.execute(
            "UPDATE model_performance SET is_active = TRUE WHERE model_version = %s",
            (model_version,)
        )
        
        # Log to audit
        cur.execute("""
            INSERT INTO audit_log (event_type, event_description, model_version)
            VALUES (%s, %s, %s)
        """, (
            'MODEL_ACTIVATED',
            f"Model {model_version} activated for production",
            model_version
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Model {model_version} is now active")
    
    def list_models(self):
        """List all registered models"""
        conn = psycopg2.connect(self.db_conn_str)
        cur = conn.cursor()
        
        query = """
            SELECT model_version, accuracy, precision_score, recall, f1_score,
                   training_date, is_active
            FROM model_performance
            ORDER BY created_at DESC
        """
        cur.execute(query)
        
        models = cur.fetchall()
        
        logger.info("Registered Models:")
        logger.info("=" * 80)
        logger.info(f"{'Version':<20} {'Acc':>6} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Active':<8} {'Date'}")
        logger.info("-" * 80)
        
        for model in models:
            version, acc, prec, rec, f1, date, active = model
            active_str = "✓" if active else ""
            logger.info(f"{version:<20} {acc:>6.3f} {prec:>6.3f} {rec:>6.3f} {f1:>6.3f} {active_str:<8} {date}")
        
        cur.close()
        conn.close()
        
        return models
    
    def get_active_model(self):
        """Get currently active model"""
        conn = psycopg2.connect(self.db_conn_str)
        cur = conn.cursor()
        
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
            logger.info(f"Active model: {result[0]}")
            logger.info(f"  Accuracy:  {result[1]:.4f}")
            logger.info(f"  Precision: {result[2]:.4f}")
            logger.info(f"  Recall:    {result[3]:.4f}")
            logger.info(f"  F1-Score:  {result[4]:.4f}")
        else:
            logger.warning("No active model found")
        
        cur.close()
        conn.close()
        
        return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Model Registry')
    parser.add_argument('--action', choices=['register', 'activate', 'list', 'active'],
                       required=True, help='Action to perform')
    parser.add_argument('--model-dir', help='Model directory (for register)')
    parser.add_argument('--model-version', help='Model version (for activate)')
    parser.add_argument('--db-host', default='localhost', help='Database host')
    
    args = parser.parse_args()
    
    conn_str = f"dbname=frauddb user=frauduser password=fraudpass host={args.db_host} port=5432"
    registry = ModelRegistry(db_conn_str=conn_str)
    
    if args.action == 'register':
        if not args.model_dir:
            logger.error("--model-dir required for register action")
            sys.exit(1)
        registry.register_model(args.model_dir)
    
    elif args.action == 'activate':
        if not args.model_version:
            logger.error("--model-version required for activate action")
            sys.exit(1)
        registry.activate_model(args.model_version)
    
    elif args.action == 'list':
        registry.list_models()
    
    elif args.action == 'active':
        registry.get_active_model()


if __name__ == "__main__":
    main()