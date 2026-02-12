#!/bin/bash

################################################################################
# Start Fraud Detection Pipeline
# Launches all components of the fraud detection system
################################################################################

set -e

echo "=========================================="
echo "Starting Fraud Detection Pipeline"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Start infrastructure with Docker Compose
echo -e "${YELLOW}Starting infrastructure...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 15

# Check Kafka
echo -e "${YELLOW}Checking Kafka...${NC}"
until docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1; do
    echo "Waiting for Kafka..."
    sleep 3
done
echo -e "${GREEN}✓ Kafka is ready${NC}"

# Check PostgreSQL
echo -e "${YELLOW}Checking PostgreSQL...${NC}"
until docker exec postgres pg_isready -U frauduser > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 3
done
echo -e "${GREEN}✓ PostgreSQL is ready${NC}"

# Check Redis
echo -e "${YELLOW}Checking Redis...${NC}"
until docker exec redis redis-cli ping > /dev/null 2>&1; do
    echo "Waiting for Redis..."
    sleep 3
done
echo -e "${GREEN}✓ Redis is ready${NC}"

# Create Kafka topic if not exists
echo -e "${YELLOW}Creating Kafka topic...${NC}"
docker exec kafka kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic banking-transactions \
    --partitions 3 \
    --replication-factor 1 \
    --if-not-exists

echo -e "${GREEN}✓ Kafka topic created${NC}"

# Install Python dependencies (if running locally)
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    # pip install -r requirements.txt --quiet
    ./venv/Scripts/python.exe -m pip install -r requirements.txt --quiet
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Infrastructure Started Successfully!${NC}"
echo "=========================================="
echo ""
echo "Services running:"
echo "  - Kafka:        http://localhost:9092"
echo "  - PostgreSQL:   localhost:5432"
echo "  - Redis:        localhost:6379"
echo "  - Spark Master: http://localhost:8080"
echo ""
echo "To start the fraud detection pipeline:"
echo "  1. Train the ML model:       ./scripts/retrain_model.sh"
echo "  2. Start transaction stream: python kafka/producer.py"
echo "  3. Start fraud detection:    python spark/streaming/spark_streaming_fraud.py"
echo "  4. Monitor metrics:          python monitoring/metrics_collector.py"
echo ""
echo "To stop:"
echo "  docker-compose down"
echo "=========================================="