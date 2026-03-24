# 🔍 Defect Monitor Server

A production-ready, automated IBM Liberty defect monitoring system with ML-powered insights, real-time dashboards, and team-specific Slack notifications.

## 🎯 Problem Statement

Manual defect monitoring is time-consuming, error-prone, and lacks visibility across teams.  
Teams often struggle with:
- Untriaged defects piling up
- Duplicate defects creating noise
- Lack of historical insights
- No centralized dashboard for tracking trends

This system solves these problems through automation, ML insights, and real-time visibility.


## ✨ Key Features

- 🤖 **ML Tag Suggestions** - Automatically categorizes defects (test_bug, product_bug, infrastructure_bug)
- 📊 **Interactive Dashboard** - Real-time defect analytics with 7-day trends
- 🔔 **Smart Notifications** - Component-wise Slack alerts with duplicate detection
- 📈 **Weekly Reports** - Automated team dashboards with insights
- 🎯 **Duplicate Detection** - Identifies similar defects (95%+ similarity)
- ⏰ **Aging Defect Alerts** - Highlights aging defects that have occurred only once and have not reoccurred.
- 🧠 **Smart Cleanup Insights** - Recommends removing low-value and duplicate defects
- 🌐 **Team-Based Monitoring** - Multi-team support with custom schedules

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Defect Monitor Server                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   IBM Auth   │  │    Defect    │  │  ML Tag      │      │
│  │              │→ │   Checker    │→ │  Suggester   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                  ↓                  ↓              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Scheduler   │  │   Database   │  │    Slack     │      │
│  │ (APScheduler)│  │   (SQLite)   │  │  Notifier    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                  ↓                  ↓              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Insights   │  │  Duplicate   │  │    Flask     │      │
│  │   Analyzer   │  │   Detector   │  │   Dashboard  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- IBM W3ID credentials
- Slack webhook URL

### Installation

1. **Clone the repository**
```bash
cd /path/to/server
git clone <repository-url>
cd defect-monitor-server
```

2. **Configure settings**
```bash
# Copy example config
cp config/config.yaml.example config/config.yaml

# Edit configuration
nano config/config.yaml
```

Update these settings:
```yaml
ibm:
  username: "your.email@ibm.com"
  password: "your_password"

slack:
  webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

teams:
  - name: "TEAM 1"
    components: ["Spring Boot", "Bean Validation"]
    slack_channel: "#Team1"
    check_time: "14:59"
    weekly_dashboard_day: "tuesday"
    weekly_dashboard_time: "15:00"

schedule:
  timezone: "Asia/Kolkata"
```

3. **Start the server**
```bash
# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify health
curl http://localhost:5001/health
```

4. **Access dashboard**
```
http://your-server-ip:5001/dashboard
```



## 📊 Dashboard Features

### Main Dashboard (`/dashboard`)
- **Metrics Cards**: Total defects, untriaged, test bugs, product bugs, infrastructure bugs
- **SLA Compliance**: Real-time compliance percentage with status indicator
- **Defect Trends**: 7-day line chart showing defect patterns
- **Component Breakdown**: Component-wise breakdown
- **Key Insights**: Duplicate detection, aging defects
- **SOE Triage Status**: Overdue defects requiring attention



## 🤖 ML Tag Suggestions

The system uses machine learning to automatically suggest tags for defects:

### Training the Model
```bash
# Initial training (requires previously triaged/tagged defects)
python retrain_model.sh

# Auto-retraining: Every weekend
```

### Tag Categories
- **test_bug**: Test infrastructure or test case issues
- **product_bug**: Actual product defects
- **infrastructure_bug**: Build, deployment, or environment issues

### Model Details
- Algorithm: Logistic Regression
- Feature Extraction: TF-IDF
- Inputs: Title, description, component, severity
- Retraining: Weekly (automated)

## 📅 Automated Schedules

### Daily Tasks
- **Team Checks**: Configured per team (e.g., 14:59 IST Mon-Fri)
- **All Components Fetch**: weekday early morning

### Weekly Tasks
- **Team Dashboards**: Configured per team (e.g., Tuesday 15:00 IST)
- **ML Model Retraining**: weekends
- **Data Cleanup**: Weekly (keeps 90 days)

## 🔧 API Endpoints

### Status & Health
- `GET /health` - Health check
- `GET /api/status` - System status and session info

### Data Access
- `GET /api/weekly-data?days=7` - Weekly analytics
- `GET /api/latest-snapshot` - Latest defect snapshot
- `GET /dashboard` - Interactive dashboard

### Manual Actions
- `POST /api/check-now` - Trigger immediate check
- `POST /api/refresh-session` - Refresh IBM session

## 📁 Project Structure

```
defect-monitor-server/
├── src/
│   ├── app.py                 # Flask application & routes
│   ├── ibm_auth.py           # IBM authentication
│   ├── defect_checker.py     # Defect fetching & processing
│   ├── slack_notifier.py     # Slack notifications
│   ├── database.py           # SQLite database operations
│   ├── scheduler.py          # Task scheduling
│   ├── ml_tag_suggester.py   # ML tag prediction
│   ├── duplicate_detector.py # Duplicate detection
│   └── insights_analyzer.py  # Insights generation
├── templates/
│   └── dashboard.html        # Dashboard UI
├── static/
│   ├── dashboard.js          # Dashboard logic
│   └── chart.min.js          # Chart.js library
├── config/
│   └── config.yaml           # Configuration
├── data/
│   ├── defects.db           # SQLite database
│   └── tag_model.pkl        # ML model
├── logs/                     # Application logs
├── docker-compose.yml        # Docker configuration
├── Dockerfile               # Docker image
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🐳 Docker Commands

```bash
# Start service
docker-compose up -d

# Stop service
docker-compose down

# View logs
docker-compose logs -f

# Restart service
./restart_server.sh

# Rebuild after changes
docker-compose build && docker-compose up -d

# Check status
docker-compose ps

# Execute commands
docker-compose exec defect-monitor python -c "print('Hello')"
```

## 🔒 Security Best Practices

- ✅ Credentials in config file (not in code)
- ✅ Use environment variables for production
- ✅ Database stored locally in container
- ✅ No external data transmission (except IBM & Slack)
- ✅ HTTPS recommended for production

## 🆘 Troubleshooting

### Service Won't Start
```bash
# Check logs
docker-compose logs

# Verify configuration
cat config/config.yaml

# Check port availability
netstat -tulpn | grep 5001
```

### Authentication Issues
```bash
# Check IBM credentials in config
# Verify VPN/network access to IBM systems

# View auth logs
docker-compose logs | grep -i auth
```

### No Slack Notifications
```bash
# Test webhook
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test"}' YOUR_WEBHOOK_URL

# Check logs
docker-compose logs | grep -i slack
```

### ML Model Issues
```bash
# Retrain model
./retrain_model.sh

# Check model file
ls -lh data/tag_model.pkl

# View training logs
docker-compose logs | grep -i "ml_tag"
```

## 📈 Monitoring & Maintenance

### Health Monitoring
```bash
# Health check
curl http://localhost:5001/health

# System status
curl http://localhost:5001/api/status

# View logs
tail -f logs/defect_monitor.log
```

### Database Backup
```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Restore backup
tar -xzf backup-20260324.tar.gz
```

### Update Application
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d
```

## 🎯 Configuration Examples

### Multi-Team Setup
```yaml
teams:
  - name: "Team Alpha"
    components: ["Spring Boot", "JPA"]
    slack_channel: "#team-alpha"
    check_time: "10:00"
    weekly_dashboard_day: "monday"
    weekly_dashboard_time: "11:00"
    
  - name: "Team Beta"
    components: ["JCA", "Bean Validation"]
    slack_channel: "#team-beta"
    check_time: "14:00"
    weekly_dashboard_day: "tuesday"
    weekly_dashboard_time: "15:00"
```

### Custom Schedules
```yaml
schedule:
  timezone: "Asia/Kolkata"
  all_components_fetch_time: "11:15"
  session_refresh_interval: 2  # hours
  data_retention_days: 90
```

## 🔮 Features

### Current Features ✅
- ✅ Real-time defect monitoring
- ✅ ML-powered tag suggestions
- ✅ Duplicate detection (95%+ similarity)
- ✅ Aging defect alerts
- ✅ Component-wise insights
- ✅ Team-specific dashboards
- ✅ Automated Slack notifications
- ✅ Interactive web dashboard
- ✅ Historical data tracking

## 📞 Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify config: `config/config.yaml`
3. Check session: `/api/status`
4. Review this README

## 📄 License

Internal IBM tool - for authorized users only.

---

**Version**: 2.0.0  
**Last Updated**: March 2026  
**Maintained By**: Development Team

**Built using Flask, SQLite, scikit-learn, and Docker**