#!/bin/bash

echo "🔍 Testing SOE Triage Data in Dashboard..."
echo ""

# Wait for check to complete
echo "⏳ Waiting 30 seconds for background fetch to complete..."
sleep 30

# Check if SOE data exists in database
echo ""
echo "📊 Checking database for SOE data..."
curl -s http://localhost:5001/api/weekly-data?days=1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
soe = data.get('soe_triage', [])
if soe:
    latest = soe[-1]
    defects = latest.get('data', {}).get('defects', [])
    print(f'✅ Found {len(defects)} SOE Triage defects in database')
    if defects:
        print(f'   Sample defect: {defects[0].get(\"id\")} - {defects[0].get(\"summary\", \"N/A\")[:50]}...')
else:
    print('❌ No SOE Triage data found in database')
"

echo ""
echo "🌐 Dashboard URL: http://localhost:5001/dashboard"
echo ""
echo "📝 Instructions:"
echo "1. Open dashboard in browser"
echo "2. Select any component (e.g., Spring Boot)"
echo "3. Click 'Load Dashboard'"
echo "4. Scroll down to 'SOE Triage: Overdue Defects' table"
echo "5. You should see the defects listed!"
echo ""

# Made with Bob
