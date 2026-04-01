#!/bin/bash

# Incremental ML Model Training Script
# Keeps existing model and adds new training data

echo "🔄 Incremental ML Model Training"
echo "===================================================="
echo ""

# Check if model exists
if [ -f "data/tag_model.pkl" ]; then
    echo "📦 Found existing model: data/tag_model.pkl"
    echo "✅ Will keep existing training data and add new defects"
else
    echo "ℹ️  No existing model found - will create new one"
fi

echo ""
echo "🚀 Restarting server to trigger incremental training..."
echo ""

# Restart Docker container
docker-compose restart

echo ""
echo "✅ Server restarted!"
echo ""
echo "📊 Incremental training will:"
echo "   ✅ Keep all previous training data"
echo "   ✅ Add new triaged defects"
echo "   ✅ Retrain on combined dataset"
echo "   ✅ Improve accuracy over time"
echo ""
echo "🔍 Monitor training progress:"
echo "   docker logs -f defect-monitor-server | grep -E 'Incremental|Training|Accuracy'"
echo ""

# Made with Bob
