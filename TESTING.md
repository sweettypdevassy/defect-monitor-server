# Testing Guide - Quick Local Test

## 🧪 Test Locally on Your Mac (Right Now!)

### Option 1: Test with Docker (Recommended - 5 minutes)

#### Step 1: Install Docker Desktop (if not installed)
```bash
# Check if Docker is installed
docker --version

# If not installed, download from:
# https://www.docker.com/products/docker-desktop
```

#### Step 2: Configure
```bash
cd /Users/sweettypdevassy/Desktop/defect-monitor-server

# Edit config with your credentials
nano config/config.yaml
```

**Minimum required changes:**
```yaml
ibm:
  username: "your.email@ibm.com"  # Your IBM email
  password: "your_password"        # Your IBM password

slack:
  webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"  # Your Slack webhook
```

#### Step 3: Build and Run
```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up

# You should see logs like:
# ✅ Configuration loaded successfully
# ✅ All services initialized successfully
# 🌐 Dashboard will be available at http://0.0.0.0:5000
```

#### Step 4: Test in Browser
Open: http://localhost:5000

You should see:
- Home page with system status
- Click "Check Now" to trigger manual check
- Click "View Dashboard" to see analytics

#### Step 5: Stop
```bash
# Press Ctrl+C to stop
# Or in another terminal:
docker-compose down
```

---

### Option 2: Test with Python Directly (10 minutes)

#### Step 1: Install Python Dependencies
```bash
cd /Users/sweettypdevassy/Desktop/defect-monitor-server

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Configure
```bash
# Edit config
nano config/config.yaml

# Update IBM credentials and Slack webhook
```

#### Step 3: Run
```bash
# Run the application
python src/app.py

# You should see:
# ✅ Configuration loaded successfully
# ✅ All services initialized successfully
# 🌐 Dashboard will be available at http://0.0.0.0:5000
```

#### Step 4: Test
Open: http://localhost:5000

#### Step 5: Stop
```bash
# Press Ctrl+C
```

---

## 🔍 Quick Test Checklist

### 1. Test Home Page
```bash
# Open browser
open http://localhost:5000

# Should show:
✓ System status
✓ Total defects count
✓ Untriaged count
✓ Components monitored
```

### 2. Test API Endpoints
```bash
# Test health check
curl http://localhost:5000/health

# Expected: {"status":"healthy","timestamp":"..."}

# Test status API
curl http://localhost:5000/api/status

# Expected: JSON with session info and scheduled jobs
```

### 3. Test Manual Check
```bash
# In browser, click "Check Now" button
# Or via API:
curl -X POST http://localhost:5000/api/check-now

# Expected: 
# - Check starts
# - Slack notification sent
# - Dashboard updates
```

### 4. Test Dashboard
```bash
# Open dashboard
open http://localhost:5000/dashboard

# Should show:
✓ KPI cards (Total, Untriaged, Test Bugs, Product Bugs)
✓ Charts (Daily Trend, Triage Status, Component Comparison)
✓ Latest snapshot table
```

---

## 🐛 Troubleshooting

### Issue: Port 5000 already in use
```bash
# Find what's using port 5000
lsof -i :5000

# Kill it or change port in config.yaml:
dashboard:
  port: 5001  # Use different port
```

### Issue: Docker not found
```bash
# Install Docker Desktop for Mac
# Download from: https://www.docker.com/products/docker-desktop

# Or use Python method instead
```

### Issue: IBM authentication fails
```bash
# Check logs
docker-compose logs | grep -i auth

# Verify:
# 1. Credentials are correct in config.yaml
# 2. VPN is connected
# 3. IBM systems are accessible
```

### Issue: Slack notifications not working
```bash
# Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test from defect monitor"}' \
  YOUR_WEBHOOK_URL

# If this works, check config.yaml webhook URL
```

---

## 📊 What to Expect

### First Run
1. **Authentication**: System logs into IBM
2. **Initial Check**: Fetches defects for all components
3. **Database Creation**: Creates SQLite database in `data/`
4. **Scheduler Start**: Sets up daily/weekly jobs
5. **Dashboard Ready**: Web interface available

### Logs to Watch For
```
✅ Configuration loaded successfully
✅ IBM authentication successful
✅ Fetched X defects for Component
✅ Daily snapshot stored
✅ Slack notifications sent successfully
✅ Scheduler started successfully
🌐 Dashboard will be available at http://0.0.0.0:5000
```

### Files Created
```
data/
  └── defects.db          # SQLite database

logs/
  └── defect_monitor.log  # Application logs
```

---

## 🎯 Quick Test Script

Save this as `test.sh` and run it:

```bash
#!/bin/bash

echo "🧪 Testing Defect Monitor Server..."

# Test 1: Health check
echo "1. Testing health endpoint..."
curl -s http://localhost:5000/health | jq

# Test 2: Status
echo "2. Testing status endpoint..."
curl -s http://localhost:5000/api/status | jq

# Test 3: Manual check
echo "3. Triggering manual check..."
curl -s -X POST http://localhost:5000/api/check-now | jq

echo "✅ Tests complete!"
echo "📊 Open http://localhost:5000 in browser"
```

Run it:
```bash
chmod +x test.sh
./test.sh
```

---

## 🚀 Next Steps After Testing

Once local testing works:

1. **Deploy to Server**
   - Follow DEPLOYMENT.md
   - Use same configuration
   - Access via server IP

2. **Share with Team**
   - Give them dashboard URL
   - Show them features
   - Get feedback

3. **Monitor**
   - Check logs daily
   - Verify notifications
   - Review dashboard

4. **Retire Extension**
   - Once stable for a week
   - Server handles everything
   - No more laptop dependency

---

## 💡 Pro Tips

1. **Test with VPN**: Make sure IBM VPN is connected
2. **Check Logs**: Always check logs if something fails
3. **Start Simple**: Test with one component first
4. **Use Docker**: Easier than Python setup
5. **Keep Running**: Leave it running for a day to test scheduling

---

## 📞 Need Help?

If you encounter issues:
1. Check logs: `docker-compose logs -f`
2. Verify config: `cat config/config.yaml`
3. Test connectivity: `curl https://libh-proxy1.fyre.ibm.com`
4. Review this guide
5. Check README.md troubleshooting section