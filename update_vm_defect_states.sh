#!/bin/bash

# Update VM database with current defect states from RTC

echo "🔄 Updating defect states in VM database..."

# Update defect #308744 state from Canceled to Open
echo "📝 Updating defect #308744 state to Open..."
sqlite3 data/defects.db "UPDATE defect_descriptions SET state = 'Open', updated_at = datetime('now') WHERE defect_id = '308744';"

# Verify the update
echo "✅ Verifying updates..."
echo ""
echo "Defect #308744:"
sqlite3 data/defects.db "SELECT defect_id, state, tags FROM defect_descriptions WHERE defect_id = '308744';"

echo ""
echo "All Bean Validation infrastructure defects:"
sqlite3 data/defects.db "SELECT defect_id, state, tags FROM defect_descriptions WHERE component = 'Bean Validation' AND (tags LIKE '%infrastructure%' OR tags LIKE '%infra%') ORDER BY defect_id;"

echo ""
echo "🔄 Now restart the Flask server:"
echo "   sudo systemctl restart defect-monitor"
echo ""
echo "✅ After restart, defect #308744 will show state as 'Open'"

# Made with Bob
