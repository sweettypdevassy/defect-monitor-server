#!/bin/bash

# Retrain ML Model Script
# Deletes old model and forces retraining with new feature weights

echo "🔄 Retraining ML Model with Updated Feature Weights"
echo "===================================================="
echo ""

# Check if model exists
if [ -f "data/tag_model.pkl" ]; then
    echo "📦 Found existing model: data/tag_model.pkl"
    echo "🗑️  Deleting old model..."
    rm data/tag_model.pkl
    echo "✅ Old model deleted"
else
    echo "ℹ️  No existing model found"
fi

echo ""
echo "🚀 Restarting server to retrain model..."
echo ""

# Restart Docker container
docker-compose restart

echo ""
echo "✅ Server restarted!"
echo ""
echo "📊 The model will retrain automatically with:"
echo "   - Summary: Equal weight"
echo "   - Description: Equal weight (now includes error patterns!)"
echo "   - Functional Area: Equal weight"
echo ""
echo "🔍 Monitor training progress:"
echo "   docker logs -f defect-monitor-server | grep -E 'Training|Accuracy'"
echo ""

# Made with Bob
