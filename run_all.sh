#!/bin/bash

################################################################################
# MASTER SCRIPT - FRAUD DETECTION SYSTEM
# Runs the complete fraud detection application with Dockerized PostgreSQL
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Python executable (adjust based on your environment)
if [ -f "./venv/Scripts/python.exe" ]; then
    PYTHON="./venv/Scripts/python.exe"
    PIP="./venv/Scripts/pip.exe"
elif [ -f "./venv/bin/python" ]; then
    PYTHON="./venv/bin/python"
    PIP="./venv/bin/pip"
else
    PYTHON="python"
    PIP="$PYTHON -m pip"
fi


echo "Using Python: $PYTHON"

# Configuration
FRAUD_RATE=0.05
TRANSACTION_DELAY=0.5
METRICS_INTERVAL=60
ALERT_INTERVAL=30

clear

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║        🏦  FRAUD DETECTION SYSTEM - MASTER LAUNCHER  🏦          ║
║                                                                   ║
║                    Real-time Fraud Detection                      ║
║                  + with Dockerized PostgreSQL                   ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo ""
echo -e "${CYAN}Starting complete fraud detection pipeline...${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for user input
pause() {
    read -p "Press [Enter] to continue..."
}

# Function to run command in background and save PID
run_background() {
    local name=$1
    local command=$2
    local log_file=$3
    
    echo -e "${YELLOW}Starting $name...${NC}"
    eval "$command > $log_file 2>&1 &"
    local pid=$!
    echo $pid > "/tmp/fraud_detection_${name// /_}.pid"
    echo -e "${GREEN}✓ $name started (PID: $pid)${NC}"
    echo -e "  Log: $log_file"
}

# Function to stop all services
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping all services...${NC}"
    
    # Kill background processes
    for pid_file in /tmp/fraud_detection_*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if ps -p $pid > /dev/null 2>&1; then
                echo "Stopping process $pid..."
                kill $pid 2>/dev/null || true
            fi
            rm "$pid_file"
        fi
    done
    
    # Stop Docker containers
    echo "Stopping Docker containers..."
    docker-compose down
    
    echo -e "${GREEN}✓ All services stopped${NC}"
}

# Trap Ctrl+C
trap cleanup EXIT INT TERM

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 1: Checking Prerequisites${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check Python
if command_exists $PYTHON || command_exists python3 || command_exists python; then
    PYTHON_VERSION=$($PYTHON --version 2>&1 || python3 --version 2>&1 || python --version 2>&1)
    echo -e "${GREEN}✓ Python: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python not found!${NC}"
    exit 1
fi

# Check Docker
if command_exists docker; then
    echo -e "${GREEN}✓ Docker: $(docker --version)${NC}"
else
    echo -e "${RED}✗ Docker not found!${NC}"
    exit 1
fi

# Check Docker Compose
if command_exists docker-compose; then
    echo -e "${GREEN}✓ Docker Compose: $(docker-compose --version)${NC}"
else
    echo -e "${RED}✗ Docker Compose not found!${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker daemon is running${NC}"

echo ""
echo -e "${GREEN}All prerequisites met!${NC}"
echo ""
sleep 2

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 2: Installing Python Dependencies${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ -f "requirements.txt" ]; then
    echo "Installing from requirements.txt..."
    $PIP install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo "Installing essential packages..."
    $PIP install -q psycopg2-binary python-dotenv redis kafka-python pandas numpy scikit-learn joblib
    echo -e "${GREEN}✓ Essential packages installed${NC}"
fi

echo ""
sleep 2

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 3: Verify PostgreSQL Database (Docker)${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo "Checking PostgreSQL container..."

if docker exec postgres pg_isready -U frauduser > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is running and reachable${NC}"
    echo -e "${GREEN}✓ Database initialized via init.sql${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not reachable${NC}"
    exit 1
fi

echo ""
sleep 2

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 4: Starting Infrastructure (Kafka, Redis, Spark)${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo "Starting Docker containers..."
docker-compose up -d

echo ""
echo "Waiting for services to start..."
sleep 15

# Check Kafka
echo -n "Checking Kafka... "
until docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1; do
    echo -n "."
    sleep 3
done
echo -e " ${GREEN}✓${NC}"

# Check Redis
echo -n "Checking Redis... "
until docker exec redis redis-cli ping > /dev/null 2>&1; do
    echo -n "."
    sleep 3
done
echo -e " ${GREEN}✓${NC}"

# Check Spark
echo -n "Checking Spark... "
sleep 5
echo -e " ${GREEN}✓${NC}"

# Create Kafka topic
echo ""
echo "Creating Kafka topic..."
docker exec kafka kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic banking-transactions \
    --partitions 3 \
    --replication-factor 1 \
    --if-not-exists > /dev/null 2>&1

echo -e "${GREEN}✓ All infrastructure services running${NC}"
echo ""
sleep 2

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 5: Training Machine Learning Model${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ ! -f "models/fraud_model_v1/data/model.pkl" ]; then
    echo "Training fraud detection model..."
    echo "This may take a minute..."
    
    $PYTHON ml/train_fraud_model.py \
        --model-type random_forest \
        --samples 50000 \
        --fraud-ratio 0.05 \
        --output-dir models/fraud_model_v1
    
    echo -e "${GREEN}✓ Model trained successfully${NC}"
else
    echo -e "${GREEN}✓ Model already exists, skipping training${NC}"
fi

echo ""
sleep 2

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 6: Starting Transaction Producer${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

mkdir -p logs

run_background \
    "Transaction Producer" \
    "$PYTHON kafka/producer.py --delay $TRANSACTION_DELAY --fraud-rate $FRAUD_RATE" \
    "logs/producer.log"

echo ""
sleep 3

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 7: Starting Fraud Detection (Spark Streaming)${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo "Starting Spark streaming job..."
echo "This runs inside the Spark container..."

docker exec -d spark-master bash -c "
spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
    /opt/spark-apps/streaming/spark_streaming_fraud.py \
    > /tmp/spark-streaming.log 2>&1
" 

echo -e "${GREEN}✓ Spark streaming started${NC}"
echo "  Log: docker exec spark-master cat /tmp/spark-streaming.log"

echo ""
sleep 3

#==============================================================================

echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}STEP 8: Starting Monitoring & Alerts${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

run_background \
    "Metrics Collector" \
    "$PYTHON monitoring/metrics_collector.py --use-neon --interval $METRICS_INTERVAL" \
    "logs/metrics.log"

run_background \
    "Alert System" \
    "$PYTHON monitoring/alerts.py --use-neon --interval $ALERT_INTERVAL" \
    "logs/alerts.log"

echo ""
sleep 3

#==============================================================================

# Convert FRAUD_RATE to percentage (Windows-safe)
FRAUD_RATE_PERCENT=$(awk "BEGIN {printf \"%d\", $FRAUD_RATE*100}")


echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}║              ${GREEN}🎉  SYSTEM FULLY OPERATIONAL  🎉${BLUE}                    ║${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}RUNNING SERVICES:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}✓${NC} Dockerized PostgreSQL : ep-sweet-pond-ah51znvo-pooler...neon.tech"
echo -e "${GREEN}✓${NC} Kafka             : localhost:9092"
echo -e "${GREEN}✓${NC} Redis             : localhost:6379"
echo -e "${GREEN}✓${NC} Spark Master      : http://localhost:8080"
echo -e "${GREEN}✓${NC} Transaction Producer (Fraud Rate: ${FRAUD_RATE_PERCENT}%)"
echo -e "${GREEN}✓${NC} Spark Streaming   : Detecting fraud in real-time"
echo -e "${GREEN}✓${NC} Metrics Collector : Collecting every ${METRICS_INTERVAL}s"
echo -e "${GREEN}✓${NC} Alert System      : Monitoring every ${ALERT_INTERVAL}s"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}LOG FILES:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Producer    : logs/producer.log"
echo "  Metrics     : logs/metrics.log"
echo "  Alerts      : logs/alerts.log"
echo "  Spark       : docker exec spark-master cat /tmp/spark-streaming.log"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}USEFUL COMMANDS:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "View producer logs       : tail -f logs/producer.log"
echo "View metrics             : tail -f logs/metrics.log"
echo "View alerts              : tail -f logs/alerts.log"
echo "View Spark logs          : docker logs -f spark-master"
echo ""
echo "View latest fraud alerts :"
echo "  docker exec -it postgres psql -U frauduser -d frauddb -c \"SELECT * FROM fraud_alerts ORDER BY detection_time DESC LIMIT 10;\""
echo ""
echo "System health check      : ./scripts/health_check.sh"
echo "View Docker services     : docker-compose ps"
echo "View Kafka topics        : docker exec kafka kafka-topics --list --bootstrap-server localhost:9092"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}MONITORING IN REAL-TIME:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Watch live transactions:"
echo "  tail -f logs/producer.log"
echo ""
echo "Watch fraud detections:"
echo "  tail -f logs/alerts.log"
echo ""

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
