-- ============================================
-- Fraud Detection Database Initialization
-- PostgreSQL compatible
-- ============================================

-- ----------------------------
-- Transactions table
-- ----------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(100) UNIQUE NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    merchant VARCHAR(200),
    transaction_time TIMESTAMP NOT NULL,
    country VARCHAR(10),
    transaction_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for transactions
CREATE INDEX IF NOT EXISTS idx_transaction_id
    ON transactions (transaction_id);

CREATE INDEX IF NOT EXISTS idx_user_id
    ON transactions (user_id);

CREATE INDEX IF NOT EXISTS idx_transaction_time
    ON transactions (transaction_time);

-- ----------------------------
-- Fraud alerts table
-- ----------------------------
CREATE TABLE IF NOT EXISTS fraud_alerts (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    merchant VARCHAR(200),
    fraud_score DECIMAL(5, 4) NOT NULL,
    is_fraud BOOLEAN NOT NULL,
    model_version VARCHAR(50),
    detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transaction_time TIMESTAMP,
    alert_status VARCHAR(50) DEFAULT 'pending',
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    notes TEXT,
    CONSTRAINT fk_transaction
        FOREIGN KEY (transaction_id)
        REFERENCES transactions(transaction_id)
        ON DELETE CASCADE
);

-- Indexes for fraud alerts
CREATE INDEX IF NOT EXISTS idx_fraud_score
    ON fraud_alerts (fraud_score);

CREATE INDEX IF NOT EXISTS idx_detection_time
    ON fraud_alerts (detection_time);

CREATE INDEX IF NOT EXISTS idx_alert_status
    ON fraud_alerts (alert_status);

CREATE INDEX IF NOT EXISTS idx_fraud_user_id
    ON fraud_alerts (user_id);

-- ----------------------------
-- Model performance table
-- ----------------------------
CREATE TABLE IF NOT EXISTS model_performance (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) NOT NULL,
    accuracy DECIMAL(5, 4),
    precision_score DECIMAL(5, 4),
    recall DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),
    training_date TIMESTAMP,
    dataset_size INTEGER,
    feature_importance JSONB,
    hyperparameters JSONB,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for model performance
CREATE INDEX IF NOT EXISTS idx_model_version
    ON model_performance (model_version);

CREATE INDEX IF NOT EXISTS idx_is_active
    ON model_performance (is_active);

-- ----------------------------
-- Audit log table
-- ----------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    event_description TEXT,
    user_id VARCHAR(50),
    transaction_id VARCHAR(100),
    model_version VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for audit log
CREATE INDEX IF NOT EXISTS idx_event_type
    ON audit_log (event_type);

CREATE INDEX IF NOT EXISTS idx_created_at
    ON audit_log (created_at);

-- ----------------------------
-- Monitoring metrics table
-- ----------------------------
CREATE TABLE IF NOT EXISTS monitoring_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15, 4),
    metric_unit VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tags JSONB
);

-- Indexes for monitoring metrics
CREATE INDEX IF NOT EXISTS idx_metric_name
    ON monitoring_metrics (metric_name);

CREATE INDEX IF NOT EXISTS idx_timestamp
    ON monitoring_metrics (timestamp);

-- ----------------------------
-- Initial model version
-- ----------------------------
INSERT INTO model_performance (
    model_version,
    accuracy,
    precision_score,
    recall,
    f1_score,
    training_date,
    is_active
)
SELECT
    'v1_initial',
    0.9500,
    0.8800,
    0.9200,
    0.9000,
    CURRENT_TIMESTAMP,
    TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM model_performance WHERE model_version = 'v1_initial'
);

-- ----------------------------
-- Analytics views
-- ----------------------------
CREATE OR REPLACE VIEW fraud_summary AS
SELECT
    DATE(detection_time) AS date,
    COUNT(*) AS total_alerts,
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS confirmed_frauds,
    AVG(fraud_score) AS avg_fraud_score,
    SUM(amount) AS total_amount_flagged,
    COUNT(DISTINCT user_id) AS unique_users_flagged
FROM fraud_alerts
GROUP BY DATE(detection_time)
ORDER BY date DESC;

CREATE OR REPLACE VIEW daily_transaction_stats AS
SELECT
    DATE(transaction_time) AS date,
    COUNT(*) AS total_transactions,
    AVG(amount) AS avg_amount,
    MAX(amount) AS max_amount,
    MIN(amount) AS min_amount,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(DISTINCT merchant) AS unique_merchants
FROM transactions
GROUP BY DATE(transaction_time)
ORDER BY date DESC;

-- ----------------------------
-- Permissions
-- ----------------------------
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO frauduser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO frauduser;

-- ----------------------------
-- Initialization log
-- ----------------------------
INSERT INTO audit_log (event_type, event_description)
VALUES ('database_init', 'Fraud detection database initialized successfully');
