#!/bin/bash

# Install ML Dependencies for Tag Suggestion Feature
# This script installs scikit-learn and numpy for the ML-based tag suggester

echo "🤖 Installing ML Dependencies for Tag Suggestion Feature"
echo "=========================================================="
echo ""

# Detect pip command (pip3 on macOS, pip on Linux)
PIP_CMD=""
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    echo "❌ Error: Neither pip nor pip3 is installed"
    echo "Please install pip first: https://pip.pypa.io/en/stable/installation/"
    exit 1
fi

echo "📦 Using: $PIP_CMD"
echo "📦 Installing scikit-learn and numpy..."
echo ""

# Install ML dependencies
$PIP_CMD install scikit-learn==1.3.2 numpy==1.24.3

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ ML dependencies installed successfully!"
    echo ""
    echo "📊 Installed packages:"
    $PIP_CMD show scikit-learn | grep "Name\|Version"
    $PIP_CMD show numpy | grep "Name\|Version"
    echo ""
    echo "🎓 The ML model will automatically train on your historical triaged defects"
    echo "   when the server starts."
    echo ""
    echo "📖 For more information, see: SETUP_ML_TAGS.md"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Restart the server: ./restart_server.sh"
    echo "   2. Check logs for training: tail -f logs/defect_monitor.log"
    echo ""
else
    echo ""
    echo "❌ Error: Failed to install ML dependencies"
    echo ""
    echo "Try installing manually:"
    echo "  pip install scikit-learn==1.3.2 numpy==1.24.3"
    echo ""
    exit 1
fi

# Made with Bob
