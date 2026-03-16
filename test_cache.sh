#!/bin/bash

echo "=========================================="
echo "🧪 Testing Description Caching"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "This test will:"
echo "1. Clear the description cache"
echo "2. Train the model (should fetch and cache ~51 descriptions)"
echo "3. Run 'Check Now' (should use cache, fetch only 2-3 new ones)"
echo ""

# Step 1: Clear cache
echo "=========================================="
echo "STEP 1: Clearing description cache"
echo "=========================================="
docker-compose exec -T defect-monitor-server python3 << 'EOF'
import sys
sys.path.insert(0, '/app/src')
from database import Database

db = Database()
# Clear cache for training components
for component in ['Classloading', 'Spring Boot']:
    count = db.clear_cached_descriptions(component)
    print(f"🗑️  Cleared {count} cached descriptions for {component}")
EOF

echo ""
echo -e "${GREEN}✅ Cache cleared${NC}"
echo ""

# Step 2: Train model
echo "=========================================="
echo "STEP 2: Training model"
echo "=========================================="
echo "⏱️  This will fetch descriptions and cache them..."
echo "Look for: '💾 Caching X descriptions to database...'"
echo ""

# Open dashboard in browser
echo "📊 Opening dashboard: http://localhost:5001"
echo ""
echo "In the dashboard:"
echo "1. Click 'Train Model' button"
echo "2. Watch the logs below for caching message"
echo "3. Training should take 2-3 minutes"
echo ""

# Show logs
echo "=========================================="
echo "📋 Watching logs (Ctrl+C to stop)..."
echo "=========================================="
docker-compose logs -f --tail=50 defect-monitor-server

# Made with Bob
