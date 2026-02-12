# 🏦 Real-Time Banking Fraud Detection System (MLOps)

A comprehensive **Big Data & MLOps** project for detecting fraudulent banking transactions in real-time using Apache Kafka, Apache Spark, Machine Learning, and PostgreSQL.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [MLOps Pipeline](#mlops-pipeline)
- [Monitoring](#monitoring)
- [Testing](#testing)
- [Future Enhancements](#future-enhancements)

---

## 🎯 Overview

This project implements a **real-time fraud detection system** for banking transactions with the following objectives:

- **Ingest** transactions in real-time via Kafka
- **Detect** fraud automatically using Machine Learning
- **Store** structured alerts in PostgreSQL and Redis
- **Monitor** system performance and model metrics
- **Scale** horizontally with Spark and Kafka

### Key Capabilities

✅ Real-time streaming with Apache Kafka  
✅ ML-based fraud prediction with Spark MLlib  
✅ Model versioning and governance  
✅ Automated alerting for critical events  
✅ Performance monitoring and metrics tracking  
✅ Docker-based deployment  

---

## 🏗️ Architecture

```
┌─────────────┐
│ Data Source │ (Transaction Generator)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Kafka    │ (Message Broker)
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Spark Streaming  │ (Stream Processing)
│  + ML Inference  │
└────────┬─────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌──────┐  ┌───────┐
│ Postgres│  │ Redis │
│(Storage)│  │(Cache)│
└─────────┘  └───────┘
```

### Data Flow

1. **Transaction Producer** → Generates/receives banking transactions
2. **Kafka** → Streams transactions to consumers
3. **Spark Streaming** → Processes transactions in real-time
4. **ML Model** → Predicts fraud probability
5. **PostgreSQL** → Stores transactions and fraud alerts
6. **Redis** → Caches recent alerts for fast access
7. **Monitoring** → Tracks metrics and triggers alerts

---

## ✨ Features

### Core Features

- **Real-time Transaction Processing**: Processes thousands of transactions per second
- **ML-based Fraud Detection**: Uses Random Forest/Gradient Boosting for predictions
- **Feature Engineering**: Automated feature creation from raw transactions
- **Model Versioning**: Track and manage multiple model versions
- **Alert System**: Automated alerts for high-value frauds and anomalies
- **Performance Monitoring**: Real-time metrics collection and reporting

### MLOps Features

- Model training pipeline
- Model evaluation and validation
- Model registry and versioning
- Batch retraining capabilities
- Prediction monitoring
- Drift detection (planned)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Ingestion** | Apache Kafka 7.5.0 |
| **Streaming** | Apache Spark 3.5.0 (Structured Streaming) |
| **ML** | Scikit-learn, Spark MLlib |
| **Storage** | PostgreSQL 15 |
| **Cache** | Redis 7 |
| **Orchestration** | Docker Compose |
| **Language** | Python 3.10+ |
| **Monitoring** | Custom metrics collector |

---

## 📁 Project Structure

```
fraud-detection-mlops/
│
├── docker-compose.yml          # Infrastructure orchestration
│
├── kafka/
│   └── producer.py            # Transaction stream generator
│
├── spark/
│   ├── streaming/
│   │   └── spark_streaming_fraud.py    # Real-time fraud detection
│   └── batch/
│       └── feature_engineering.py      # Batch feature processing
│
├── ml/
│   ├── train_fraud_model.py           # Model training
│   ├── evaluate_model.py              # Model evaluation
│   └── model_registry.py              # Model versioning
│
├── models/
│   └── fraud_model_v1/                # Trained models
│       ├── data/
│       │   ├── model.pkl
│       │   ├── scaler.pkl
│       │   └── label_encoders.pkl
│       └── metadata/
│           └── model_info.json
│
├── storage/
│   ├── postgres/
│   │   └── init.sql                   # Database schema
│   └── redis/
│
├── monitoring/
│   ├── metrics_collector.py           # Metrics collection
│   └── alerts.py                      # Alert system
│
├── scripts/
│   ├── start_pipeline.sh              # Start all services
│   ├── retrain_model.sh               # Retrain ML model
│   └── health_check.sh                # System health check
│
├── data/
│   └── historical_transactions.csv    # Training data
│
└── README.md
```

---

## 🔧 Prerequisites

- **Docker** 20.10+ and Docker Compose
- **Python** 3.10+
- **Git**
- 8GB+ RAM recommended
- 20GB+ disk space

---

## 📦 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd fraud-detection-mlops
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt**:
```
kafka-python==2.0.2
pyspark==3.5.0
scikit-learn==1.3.2
pandas==2.1.3
numpy==1.26.2
psycopg2-binary==2.9.9
redis==5.0.1
joblib==1.3.2
matplotlib==3.8.2
seaborn==0.13.0
```

### 3. Start Infrastructure

```bash
chmod +x scripts/*.sh
./scripts/start_pipeline.sh
```

This will start:
- Kafka & Zookeeper
- PostgreSQL
- Redis
- Spark cluster

### 4. Train ML Model

```bash
./scripts/retrain_model.sh
```

---

## 🚀 Usage

### Step 1: Start Transaction Producer

```bash
python kafka/producer.py --delay 0.5 --fraud-rate 0.05
```

**Arguments**:
- `--delay`: Seconds between transactions (default: 1.0)
- `--fraud-rate`: Fraud probability 0-1 (default: 0.05)
- `--num`: Number of transactions (default: infinite)

### Step 2: Start Fraud Detection Streaming

```bash
# In Docker container or with proper Spark setup
python spark/streaming/spark_streaming_fraud.py
```

### Step 3: Start Monitoring

```bash
# Metrics collector
python monitoring/metrics_collector.py --interval 60

# Alert system
python monitoring/alerts.py --interval 30
```

### Step 4: Query Results

**PostgreSQL**:
```bash
docker exec -it postgres psql -U frauduser -d frauddb

-- View fraud alerts
SELECT * FROM fraud_alerts WHERE is_fraud = TRUE ORDER BY detection_time DESC LIMIT 10;

-- View fraud summary
SELECT * FROM fraud_summary;
```

**Redis**:
```bash
docker exec -it redis redis-cli

# Get cached alerts
KEYS fraud_alert:*
GET fraud_alert:TXN_123456
```

---

## 🔄 MLOps Pipeline

### Training Pipeline

```bash
# 1. Train new model
python ml/train_fraud_model.py \
    --model-type random_forest \
    --samples 50000 \
    --fraud-ratio 0.05 \
    --output-dir models/fraud_model_v2

# 2. Evaluate model
python ml/evaluate_model.py --model-dir models/fraud_model_v2

# 3. Register model
python ml/model_registry.py --action register --model-dir models/fraud_model_v2

# 4. Activate model
python ml/model_registry.py --action activate --model-version v2
```

### Model Versioning

```bash
# List all models
python ml/model_registry.py --action list

# Get active model
python ml/model_registry.py --action active
```

---

## 📊 Monitoring

### Available Metrics

**Transaction Metrics**:
- Transactions per minute
- Average transaction amount
- Daily transaction count

**Fraud Metrics**:
- Fraud detection rate
- Average fraud score
- Pending alerts

**Model Metrics**:
- Accuracy, Precision, Recall, F1-Score
- Active model version

**System Health**:
- Service status (Kafka, Postgres, Redis)
- Cache size
- Processing latency

### Health Check

```bash
./scripts/health_check.sh
```

---

## 🧪 Testing

### Test Scenarios

**1. Normal Transaction**:
```json
{
  "amount": 50.00,
  "merchant": "Walmart",
  "hour": 14,
  "country": "US"
}
```
Expected: `is_fraud = False`, `fraud_score < 0.3`

**2. High-Value Fraud**:
```json
{
  "amount": 3500.00,
  "merchant": "Unknown Merchant",
  "hour": 2,
  "country": "RU"
}
```
Expected: `is_fraud = True`, `fraud_score > 0.8`

### Unit Tests

```bash
# Run model tests
python -m pytest tests/test_model.py

# Run streaming tests
python -m pytest tests/test_streaming.py
```

---

## 🔮 Future Enhancements

### Planned Features

- [ ] **Grafana Dashboard**: Real-time visualization
- [ ] **MLflow Integration**: Advanced experiment tracking
- [ ] **Kubernetes Deployment**: Cloud-native orchestration
- [ ] **Online Learning**: Continuous model updates
- [ ] **SHAP Explainability**: Model interpretability
- [ ] **A/B Testing**: Multi-model comparison
- [ ] **Drift Detection**: Automatic concept drift alerts
- [ ] **Web Interface**: User-friendly fraud review portal

### Scalability Improvements

- [ ] Kafka partitioning strategy
- [ ] Spark cluster auto-scaling
- [ ] Distributed model serving
- [ ] Time-series database for metrics

---

## 📝 Configuration

### Environment Variables

```bash
# Kafka
KAFKA_BROKERS=localhost:9092
KAFKA_TOPIC=banking-transactions

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=frauduser
POSTGRES_PASSWORD=fraudpass
POSTGRES_DB=frauddb

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Model
MODEL_PATH=models/fraud_model_v1
```

---

## 🐛 Troubleshooting

### Common Issues

**Kafka not starting**:
```bash
# Check Zookeeper
docker logs zookeeper

# Recreate Kafka
docker-compose restart kafka
```

**PostgreSQL connection refused**:
```bash
# Check if PostgreSQL is ready
docker exec postgres pg_isready -U frauduser
```

**Model not found**:
```bash
# Train model first
./scripts/retrain_model.sh
```

---

## 📄 License

This project is licensed under the MIT License.

---

## 👥 Contributors

- Data Engineering Team
- ML Engineering Team
- DevOps Team

---

## 📧 Contact

For questions or support, please contact: [your-email@example.com]

---

## 🙏 Acknowledgments

- Apache Kafka community
- Apache Spark community
- Scikit-learn contributors
- Open source community

---

**Built with ❤️ for real-time fraud detection**