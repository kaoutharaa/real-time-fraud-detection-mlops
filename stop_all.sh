#!/bin/bash

################################################################################
# STOP ALL SERVICES - Fraud Detection System
# Stops all running components gracefully
################################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}═════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Stopping Fraud Detection System${NC}"
echo -e "${BLUE}═════════════════════════════════════════════════${NC}"
echo ""

# Stop background Python processes
echo -e "${YELLOW}Stopping Python processes...${NC}"
for pid_file in /tmp/fraud_detection_*.pid; do
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        service_name=$(basename "$pid_file" .pid | sed 's/fraud_detection_//' | sed 's/_/ /g')
        
        if ps -p $pid > /dev/null 2>&1; then
            echo "  Stopping: $service_name (PID: $pid)"
            kill $pid 2>/dev/null || true
            sleep 1
            
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                kill -9 $pid 2>/dev/null || true
            fi
        fi
        
        rm "$pid_file"
    fi
done

echo -e "${GREEN}✓ Python processes stopped${NC}"
echo ""

# Stop Spark streaming job
echo -e "${YELLOW}Stopping Spark streaming job...${NC}"
docker exec spark-master pkill -f spark-streaming 2>/dev/null || true
echo -e "${GREEN}✓ Spark job stopped${NC}"
echo ""

# Stop Docker containers
echo -e "${YELLOW}Stopping Docker containers...${NC}"
docker-compose down

echo -e "${GREEN}✓ Docker containers stopped${NC}"
echo ""

# Clean up log files (optional)
read -p "Do you want to delete log files? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cleaning log files...${NC}"
    rm -f logs/*.log
    echo -e "${GREEN}✓ Log files deleted${NC}"
else
    echo -e "${BLUE}Log files kept in logs/ directory${NC}"
fi

echo ""
echo -e "${GREEN}═════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  All services stopped successfully!${NC}"
echo -e "${GREEN}═════════════════════════════════════════════════${NC}"
echo ""
echo "To restart the system, run:"
echo "  ./run_all.sh"
echo ""