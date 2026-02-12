#!/bin/bash

################################################################################
# Health Check Script
# Verifies all system components are running correctly
################################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Fraud Detection System Health Check"
echo "=========================================="
echo ""

# Track overall health
ALL_HEALTHY=true

# Check Docker
echo -n "Docker:              "
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ALL_HEALTHY=false
fi

# Check Zookeeper
echo -n "Zookeeper:           "
if docker ps | grep -q zookeeper; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ALL_HEALTHY=false
fi

# Check Kafka
echo -n "Kafka:               "
if docker ps | grep -q kafka; then
    if docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running & Responsive${NC}"
    else
        echo -e "${YELLOW}⚠ Running but not responsive${NC}"
        ALL_HEALTHY=false
    fi
else
    echo -e "${RED}✗ Not running${NC}"
    ALL_HEALTHY=false
fi

# Check PostgreSQL
echo -n "PostgreSQL:          "
if docker ps | grep -q postgres; then
    if docker exec postgres pg_isready -U frauduser > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running & Responsive${NC}"
    else
        echo -e "${YELLOW}⚠ Running but not responsive${NC}"
        ALL_HEALTHY=false
    fi
else
    echo -e "${RED}✗ Not running${NC}"
    ALL_HEALTHY=false
fi

# Check Redis
echo -n "Redis:               "
if docker ps | grep -q redis; then
    if docker exec redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running & Responsive${NC}"
    else
        echo -e "${YELLOW}⚠ Running but not responsive${NC}"
        ALL_HEALTHY=false
    fi
else
    echo -e "${RED}✗ Not running${NC}"
    ALL_HEALTHY=false
fi

# Check Spark Master
echo -n "Spark Master:        "
if docker ps | grep -q spark-master; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ALL_HEALTHY=false
fi

# Check Spark Worker
echo -n "Spark Worker:        "
if docker ps | grep -q spark-worker; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ALL_HEALTHY=false
fi

echo ""
echo "=========================================="
echo "Database Health"
echo "=========================================="

# Check database tables
if docker exec postgres psql -U frauduser -d frauddb -c "\dt" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Database tables exist${NC}"
    
    # Count records
    TX_COUNT=$(docker exec postgres psql -U frauduser -d frauddb -t -c "SELECT COUNT(*) FROM transactions;" 2>/dev/null | tr -d ' ')
    ALERT_COUNT=$(docker exec postgres psql -U frauduser -d frauddb -t -c "SELECT COUNT(*) FROM fraud_alerts;" 2>/dev/null | tr -d ' ')
    
    echo "  Transactions:      $TX_COUNT"
    echo "  Fraud Alerts:      $ALERT_COUNT"
else
    echo -e "${RED}✗ Database tables not initialized${NC}"
    ALL_HEALTHY=false
fi

echo ""
echo "=========================================="
echo "Model Status"
echo "=========================================="

# Check if model exists
if [ -d "models/fraud_model_v1" ]; then
    echo -e "${GREEN}✓ ML Model exists${NC}"
    
    if [ -f "models/fraud_model_v1/metadata/model_info.json" ]; then
        MODEL_VERSION=$(grep -o '"version": "[^"]*"' models/fraud_model_v1/metadata/model_info.json | cut -d'"' -f4)
        echo "  Model Version:     $MODEL_VERSION"
    fi
else
    echo -e "${YELLOW}⚠ ML Model not trained yet${NC}"
    echo "  Run: ./scripts/retrain_model.sh"
fi

echo ""
echo "=========================================="

if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}System Status: ALL SYSTEMS OPERATIONAL${NC}"
    exit 0
else
    echo -e "${RED}System Status: ISSUES DETECTED${NC}"
    echo ""
    echo "To start services: ./scripts/start_pipeline.sh"
    exit 1
fi