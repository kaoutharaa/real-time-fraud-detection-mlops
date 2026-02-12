# Quick Start Guide - Fraud Detection MLOps

Get the fraud detection system running in **5 minutes**!

---

## ⚡ Quick Setup

### Prerequisites
```bash
# Ensure you have:
- Docker & Docker Compose installed
- Python 3.10+
- 8GB RAM minimum
```

### Step 1: Start Infrastructure (2 minutes)
```bash
# Start all services
./scripts/start_pipeline.sh

# Wait for services to be ready...
# You should see: ✓ All systems operational
```

### Step 2: Train ML Model (1 minute)
```bash
# Train the fraud detection model
./scripts/retrain_model.sh

# This creates: models/fraud_model_v1/
```

### Step 3: Start Fraud Detection (30 seconds)
```bash
# Terminal 1: Start transaction producer
python kafka/producer.py --delay 0.5

# Terminal 2: Start fraud detection (requires Spark)
# NOTE: Run this inside spark container or with local Spark
docker exec -it spark-master bash -c "/opt/spark/bin/spark-submit --master spark://spark-master:7077 --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 --conf spark.jars.ivy=/tmp/.ivy2 /opt/spark-apps/streaming/spark_streaming_fraud.py"

```

### Step 4: Monitor Results (30 seconds)
```bash
# Terminal 3: Check fraud alerts
docker exec -it postgres psql -U frauduser -d frauddb

# Run SQL:
SELECT * FROM transactions ORDER BY transaction_time DESC LIMIT 10;
```

---

## 📊 View Live Metrics

```bash
# In a new terminal
docker run --rm --network mlops_fraud-network metrics-collector python monitoring/metrics_collector.py --once --postgres-host postgres --redis-host redis


# Output shows:
# - Transactions per minute
# - Fraud detection rate
# - Model performance
# - System health
```

---

## ✅ Verify Everything Works

```bash
# Run health check
./scripts/health_check.sh

# Should show all green ✓ checkmarks
```

---

## 🎯 What's Happening?

1. **Kafka Producer** generates realistic banking transactions
2. **Kafka** streams them to Spark
3. **Spark** processes each transaction through the ML model
4. **ML Model** predicts fraud probability
5. **PostgreSQL** stores transactions and alerts
6. **Redis** caches recent fraud alerts

---

## 🔍 Next Steps

### View Fraud Alerts in Real-Time
```bash
# Watch Redis cache
docker exec -it redis redis-cli
> KEYS fraud_alert:*
> GET fraud_alert:<transaction_id>
```

### Check System Health
```bash
./scripts/health_check.sh
```

### Retrain Model with New Data
```bash
# Adjust parameters
export MODEL_TYPE=gradient_boosting
export SAMPLES=100000
export FRAUD_RATIO=0.08

./scripts/retrain_model.sh
```

### Start Alert Monitoring
```bash
docker run --rm --network mlops_fraud-network metrics-collector \
  python monitoring/alerts.py --redis-host redis --postgres-host postgres

```

---

## 🐛 Troubleshooting

### Kafka Not Starting?
```bash
docker-compose restart kafka
docker logs kafka
```

### Model Not Found?
```bash
# Train it first!
./scripts/retrain_model.sh
```

### Port Already in Use?
```bash
# Check what's using the ports
sudo lsof -i :9092  # Kafka
sudo lsof -i :5432  # PostgreSQL
sudo lsof -i :6379  # Redis

# Stop conflicting services
docker-compose down
```

---

## 📖 Full Documentation

See [README.md](README.md) for comprehensive documentation.

---

## 🎉 Success Indicators

You're all set when you see:
- ✅ Services running (via health check)
- ✅ Transactions being produced (console logs)
- ✅ Fraud alerts in database
- ✅ Metrics being collected

**Happy Fraud Detecting! 🎯**