#!/bin/bash

################################################################################
# Retrain Fraud Detection Model
################################################################################

set -e

# Path to venv Python
VENV_PYTHON="D:/chadi/mlops/venv/Scripts/python.exe"

echo "=========================================="
echo "Retraining Fraud Detection Model"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
MODEL_DIR="models/fraud_model_$(date +%Y%m%d_%H%M%S)"
MODEL_TYPE="${MODEL_TYPE:-gradient_boosting}"
SAMPLES="${SAMPLES:-100000}"
FRAUD_RATIO="${FRAUD_RATIO:-0.08}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Model Type:    $MODEL_TYPE"
echo "  Samples:       $SAMPLES"
echo "  Fraud Ratio:   $FRAUD_RATIO"
echo "  Output Dir:    $MODEL_DIR"
echo ""

# Train the model using venv Python
echo -e "${YELLOW}Training model...${NC}"
"$VENV_PYTHON" ml/train_fraud_model.py \
    --model-type "$MODEL_TYPE" \
    --samples "$SAMPLES" \
    --fraud-ratio "$FRAUD_RATIO" \
    --output-dir "$MODEL_DIR"

echo -e "${GREEN}✓ Model training completed${NC}"

# Evaluate model (optional)
if [ -f "ml/evaluate_model.py" ]; then
    echo -e "${YELLOW}Evaluating model...${NC}"
    "$VENV_PYTHON" ml/evaluate_model.py --model-dir "$MODEL_DIR"
fi

# Update symlink to latest model
 
echo -e "${YELLOW}Updating production model folder...${NC}"

# Ensure the models folder exists
mkdir -p models

# Find the latest model folder (sorted by name)
LATEST_MODEL=$(ls -d models/fraud_model_* | sort | tail -n 1)

# Remove old 'latest' folder if it exists
rm -rf models/fraud_model_latest

# Copy the newest model folder as 'latest'
cp -r "$LATEST_MODEL" models/fraud_model_latest

echo -e "${GREEN}✓ Production model folder updated to latest: $LATEST_MODEL${NC}"



# Register model version in database
if [ -f "ml/model_registry.py" ]; then
    echo -e "${YELLOW}Registering model in database...${NC}"
    "$VENV_PYTHON" ml/model_registry.py --model-dir "$MODEL_DIR" --action register
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Model Retraining Complete!${NC}"
echo "=========================================="
echo "Model Location: $MODEL_DIR"
echo ""
