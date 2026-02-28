# 🏦 Real-Time Banking Fraud Detection System

A full-stack MLOps project that detects fraudulent banking transactions as they happen — built with Kafka, Spark, a trained ML model, and a live WebSocket dashboard.

---

## What it does

Transactions flow in from a producer, get streamed through Kafka, processed by Spark with a Random Forest model, and flagged results land in PostgreSQL — all within seconds. A FastAPI backend pushes everything live to a dashboard via WebSocket.

```
Producer → Kafka → Spark + ML Model → PostgreSQL / Redis → FastAPI → Dashboard
```

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Streaming | Apache Kafka |
| Processing | Apache Spark 3.5 (Structured Streaming) |
| ML | Scikit-learn (Random Forest) |
| Storage | PostgreSQL 15 |
| Cache | Redis 7 |
| Backend | FastAPI + WebSocket |
| Frontend | HTML/CSS/JS (Chart.js) |
| Infra | Docker Compose |

---

## Getting Started

### Prerequisites
- Docker + Docker Compose
- Python 3.10+
- 8GB RAM minimum

### Run everything with one command

# Start infrastructure
```bash
./run.sh
```
# Start FastAPI backend```
python -m uvicorn api:app --reload --port 8000
``

Then open **http://localhost:8000** in your browser.

---

## Dashboard

The dashboard gives you a real-time view of everything:

- **Assets\screenshots\dashboard-overview.png** — new rows appear within 1 second via WebSocket
- **Assets\screenshots\fraud-alert-banner.png** — detection rate, average score, pending alerts
- **Assets\screenshots\fraud-by-region.png** — geographic breakdown of detected fraud
- **Assets\screenshots\transaction-vs-fraud-chart.png** — transactions and fraud events over time
- **Assets\screenshots\pipeline-health.png** — status of all 6 services with latency
- **Assets\screenshots\ml-performance.png** — precision, recall, F1, accuracy

---

## How the ML model works

The model is trained on 50,000 synthetic transactions (5% fraud rate) using these features:

| Feature | Description |
|---------|-------------|
| `amount` / `amount_log` | Transaction value |
| `hour` / `day_of_week` | Time patterns |
| `is_night` / `is_weekend` | High-risk time windows |
| `is_high_amount` | Above threshold flag |
| `is_unknown_merchant` | Unknown merchant flag |
| `is_foreign_country` | Cross-border flag |
| `user_frequency` | How often this user transacts |
| `merchant/country/type encoded` | Label-encoded categoricals |

Achieves **~99.6% accuracy**, **0.95 precision**, **0.98 recall** on test set.

---

## Useful commands

```bash
# Check if transactions are flowing
docker exec postgres psql -U frauduser -d frauddb -c "SELECT COUNT(*) FROM transactions;"

# Check fraud detections
docker exec postgres psql -U frauduser -d frauddb -c "SELECT COUNT(*) FROM fraud_alerts WHERE is_fraud = TRUE;"

# Watch Spark logs live
docker exec spark-master bash -c "tail -f /tmp/spark-streaming.log"

# View producer output
tail -f logs/producer.log
```

---

## Troubleshooting

**Dashboard shows 0s** → Make sure the producer is running and Spark has been up for at least 30 seconds.

**WebSocket not connecting** → Restart uvicorn, make sure you're opening `http://localhost:8000` not the HTML file directly.

---

 