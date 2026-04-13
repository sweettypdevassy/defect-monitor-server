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

## ✨ Features Overview

### A. Smart Slack Notifications 🔔

The system automatically sends daily updates to team-specific Slack channels with intelligent grouping and insights.

**Key Capabilities:**
- ✅ Automated daily notifications at configured times (e.g., 10:00 IST)
- ✅ Component-wise grouping for easy review
- ✅ ML-powered tag suggestions included in notifications
- ✅ Duplicate defect alerts with similarity scores
- ✅ SOE triage status highlighting
- ✅ Direct links to IBM defect system and dashboard
- ✅ Team-specific Slack channels and webhooks

Defects are neatly grouped by components (like Spring Boot, JPA), making them easier to review. The system highlights untriaged defects, flags potential duplicates, and even suggests tags using machine learning. It also calls out overdue SOE triage items and includes direct links to defect details and the dashboard for quick access.

### B. Interactive Web Dashboard 📊

A real-time dashboard gives a clear view of defect trends and insights with 90 days of historical data.

**Key Features:**
- ✅ Real-time metrics cards (total, untriaged, by tag)
- ✅ 7-day trend visualization with Chart.js
- ✅ Component-wise breakdown charts
- ✅ Tag distribution analysis
- ✅ SLA compliance tracking with status indicators
- ✅ 90-day historical data retention
- ✅ Browser-accessible at `https://defectmonitoring.dev.fyre.ibm.com/dashboard`
- ✅ Auto-refresh capability for live updates
- ✅ Best Practices & Insights showing duplicates and aged defects
- ✅ SOE Triage: Overdue Defect tracking
- ✅ All Untriaged Defects view
- ✅ Defects by Component breakdown

The dashboard includes overview cards, detailed component views, and AI-driven insights. Teams can analyze patterns over time with interactive charts and real-time updates.

### C. ML-Powered Insights & Tag Suggestions 🤖

The system uses machine learning to enhance defect analysis in multiple ways.

#### 1. Tag Suggestions

Automatically suggests tags such as `test_bug`, `product_bug`, and `infrastructure_bug` by analyzing defect summaries, descriptions, and components using TF-IDF and a Logistic Regression model.

**Technical Details:**
- **Algorithm**: Logistic Regression with TF-IDF vectorization
- **Features**: Title, description, component, severity
- **Accuracy**: More than 50% on trained models
- **Weekly retraining**: Incremental learning with new data
- **Training schedule**: Configurable (e.g., Saturday 10:00 IST)

The model retrains weekly using historical data to improve accuracy over time.

#### 2. Aging Defect Detection

The system identifies low-value, aging defects that may no longer require attention. These are defects that are older than 1 month, have occurred in only a single build, and show no signs of recurring impact.

**Detection Criteria:**
- **Age threshold**: >1 Month old
- **Occurrence**: Single build only
- **Impact**: No recurrence detected
- **Recommendation**: Safe for cancellation
- **Benefit**: Reduces backlog noise

Such defects are typically transient or non-reproducible, and can therefore be safely considered for cancellation, helping teams reduce backlog noise and focus on more critical issues.

#### 3. Duplicate Defect Detection (ML Insight)

The system identifies defects that are highly similar (more than 80% match), indicating potential duplicates.

**Technical Implementation:**
- **Algorithm**: TF-IDF + Cosine Similarity
- **Threshold**: 80%+ similarity
- **Comparison**: Title + description combined
- **Grouped duplicates** with scores
- **Recommendation**: Retain one, cancel others

In such cases, teams can consider retaining a single valid defect while cancelling the others to avoid redundancy and improve tracking efficiency.

### D. Team-Based Monitoring 👥

Multiple teams can use the system with their own configurations. Each team can define components, schedules, and Slack channels.

**Configuration Options:**
- ✅ Team-specific component lists
- ✅ Custom check schedules per team
- ✅ Independent Slack webhooks and channels
- ✅ Weekend skip option (`skip_weekends: true/false`)
- ✅ Weekly dashboard day and time per team
- ✅ Unlimited team support
- ✅ Isolated notifications and reports

It also supports skipping weekends and generating weekly summaries tailored to each team.

### E. Weekly Dashboard Reports 📈

A weekly summary is sent to Slack with key metrics and actionable insights.

**Report Contents:**
- ✅ Total defects count
- ✅ Untriaged defects count
- ✅ Tag distribution (test_bug, product_bug, infrastructure_bug)
- ✅ Component breakdown
- ✅ Aging defect alerts
- ✅ Duplicate detection results
- ✅ Direct dashboard link

**Scheduling:**
- Configurable day (e.g., Tuesday, Saturday)
- Configurable time (e.g., 15:00 IST)
- Team-specific delivery
- Automated generation

The report includes week-over-week changes and a link to the full dashboard for detailed analysis.

### F. Historical Data Tracking 📚

The system stores daily snapshots in a SQLite database, maintaining up to 90 days of history.

**Database Features:**
- ✅ SQLite database with optimized indexes
- ✅ Daily defect snapshots
- ✅ 90-day retention (configurable)
- ✅ Automatic cleanup of old data
- ✅ ML training data storage
- ✅ Comparison of new vs. existing defects
- ✅ Historical trend analysis
- ✅ Component-wise tracking
- ✅ Tag evolution monitoring

**Data Tables:**
- `defects`: Main defect records
- `snapshots`: Historical snapshots
- `ml_training_data`: Tagged defects for ML

This enables trend analysis, component tracking, and monitoring how tags evolve over time.

### G. Flexible Scheduling ⏰

All tasks are automated and configurable. Daily checks, weekly reports, ML retraining, and data cleanup run on schedules aligned with IST.

**Scheduled Tasks:**
- **Team Checks**: Configurable per team (e.g., Mon-Fri 10:00 IST)
- **Weekly Dashboards**: Per team (e.g., Tuesday 15:00 IST)
- **ML Retraining**: Weekly (e.g., Thursday 12:17 IST)
- **Background Fetch**: Daily all-components (e.g., 14:15 IST)
- **Cache Cleanup**: Weekly
- **Data Cleanup**: Weekly (90-day retention)

**Technology:**
- APScheduler (Background Scheduler)
- Timezone support (Asia/Kolkata)
- Cron-style triggers
- Non-blocking execution

Background processes keep dashboard data up to date without manual intervention.

### H. Robust IBM Authentication 🔐

The system uses Playwright (headless browser automation) to handle IBM's complex W3ID authentication.

**Authentication Features:**
- ✅ Automated W3ID login
- ✅ Cookie persistence across restarts
- ✅ 8-hour session timeout handling
- ✅ Automatic session refresh every 2 hours
- ✅ 2FA support
- ✅ Chrome profile integration
- ✅ Network error handling
- ✅ Graceful timeout recovery

**Why Playwright:**
IBM's authentication requires JavaScript execution and complex cookie handling that standard HTTP libraries cannot handle. Playwright provides a robust solution with session management and cookie persistence.

### I. RESTful API Endpoints 🌐

Programmatic access to system data and operations.

**Available Endpoints:**
- `GET /health` - Health check
- `GET /api/status` - System status and session info
- `GET /api/weekly-data?days=7` - Analytics data
- `GET /api/latest-snapshot` - Latest defect snapshot
- `GET /dashboard` - Interactive dashboard UI
- `POST /api/check-now` - Trigger immediate check
- `POST /api/refresh-session` - Refresh IBM session

**Response Format:** JSON

All endpoints return structured JSON responses for easy integration with other tools.

### J. Docker Containerization 🐳

Fully containerized deployment for easy setup and consistent environments.

**Docker Features:**
- ✅ Single-command deployment (`docker-compose up -d`)
- ✅ Persistent volumes (data, logs, config, Chrome profile)
- ✅ Health checks with auto-restart
- ✅ Port mapping (5001:5000)
- ✅ Timezone configuration (Asia/Kolkata)
- ✅ Volume mounts for live code updates
- ✅ Named volumes for Playwright cache
- ✅ Network isolation

**Benefits:**
- Easy deployment on any system
- Consistent environment
- Portable across servers
- Automatic recovery from failures

### K. Comprehensive Logging 📝

Detailed logging for debugging, monitoring, and audit trails.

**Logging Features:**
- ✅ Multiple log levels (INFO, WARNING, ERROR)
- ✅ File logging (`logs/defect_monitor.log`)
- ✅ Console output for Docker logs
- ✅ Automatic log rotation
- ✅ Timestamped entries
- ✅ Component-specific logging

**Logged Events:**
- Authentication attempts
- Defect checks
- ML predictions
- Slack notifications
- Errors and exceptions
- Schedule executions

### L. VM Deployment 🖥️

The application has been successfully deployed on a VM for continuous operation with functional ID configuration and verified end-to-end functionality.

**Deployment Features:**
- Production-ready VM setup
- Functional ID authentication
- Continuous 24/7 operation
- Verified end-to-end workflows
- Stable production environment

### M. Secure Public Access (HTTPS Enablement) 🔒

The dashboard is now accessible via secure HTTPS with proper SSL/TLS certificate configuration, ensuring encrypted and secure access.

**Security Features:**
- HTTPS-enabled dashboard
- SSL/TLS certificate configuration
- Encrypted data transmission
- Secure public access
- Production-grade security

### N. Real-Time System Monitoring & Notifications 🔔

The system provides comprehensive real-time monitoring through Slack notifications, ensuring you're always informed about all system activities, successes, and issues.

**Notification Types:**
- ✅ Component Fetch Notifications
- ✅ ML Model Training Notifications
- ✅ Defect Notification Confirmations
- ✅ Error & Authentication Alerts

Everything works fine with proactive notifications for every major event, providing complete visibility into system operations.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Defect Monitor Server                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   IBM Auth   │  │    Defect    │  │  ML Tag      │      │
│  │ (Playwright) │→ │   Checker    │→ │  Suggester   │      │
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
https://defectmonitoring.dev.fyre.ibm.com/dashboard
```

## 📊 Dashboard Features

### Main Dashboard (`/dashboard`)
- **Metrics Cards**: Total defects, untriaged, test bugs, product bugs, infrastructure bugs
- **SLA Compliance**: Real-time compliance percentage with status indicator
- **Defect Trends**: 7-day line chart showing defect patterns
- **Component Breakdown**: Component-wise breakdown with interactive charts
- **Key Insights**: Duplicate detection, aging defects
- **SOE Triage Status**: Overdue defects requiring attention
- **Tag Distribution**: Visual breakdown of defect categories
- **Historical Analysis**: 90-day trend analysis

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
- **Algorithm**: Logistic Regression
- **Feature Extraction**: TF-IDF
- **Inputs**: Title, description, component, severity
- **Accuracy**: >50% on trained models
- **Retraining**: Weekly (automated)

## 📅 Automated Schedules

### Daily Tasks
- **Team Checks**: Configured per team (e.g., 14:59 IST Mon-Fri)
- **All Components Fetch**: Weekday early morning
- **Session Refresh**: Every 2 hours

### Weekly Tasks
- **Team Dashboards**: Configured per team (e.g., Tuesday 15:00 IST)
- **ML Model Retraining**: Weekends
- **Data Cleanup**: Weekly (keeps 90 days)
- **Cache Cleanup**: Weekly

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
│   ├── ibm_auth.py           # IBM authentication (Playwright)
│   ├── browser_manager.py    # Browser automation
│   ├── defect_checker.py     # Defect fetching & processing
│   ├── slack_notifier.py     # Slack notifications
│   ├── database.py           # SQLite database operations
│   ├── scheduler.py          # Task scheduling (APScheduler)
│   ├── ml_tag_suggester.py   # ML tag prediction
│   ├── duplicate_detector.py # Duplicate detection
│   ├── insights_analyzer.py  # Insights generation
│   └── cache_cleaner.py      # Cache management
├── templates/
│   └── dashboard.html        # Dashboard UI
├── static/
│   ├── dashboard.js          # Dashboard logic
│   └── chart.min.js          # Chart.js library
├── config/
│   └── config.yaml           # Configuration
├── data/
│   ├── defects.db           # SQLite database
│   ├── tag_model.pkl        # ML model
│   └── chrome_profile/      # Browser profile
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
- ✅ HTTPS enabled for production
- ✅ SSL/TLS certificate configuration
- ✅ Encrypted data transmission
- ✅ Secure cookie handling

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

# Refresh session manually
curl -X POST http://localhost:5001/api/refresh-session
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
    skip_weekends: true
    
  - name: "Team Beta"
    components: ["JCA", "Bean Validation"]
    slack_channel: "#team-beta"
    check_time: "14:00"
    weekly_dashboard_day: "tuesday"
    weekly_dashboard_time: "15:00"
    skip_weekends: true
```

### Custom Schedules
```yaml
schedule:
  timezone: "Asia/Kolkata"
  all_components_fetch_time: "11:15"
  session_refresh_interval: 2  # hours
  data_retention_days: 90
  ml_retrain_day: "saturday"
  ml_retrain_time: "10:00"
```

## 🎓 Best Practices

### For Teams
1. Review daily Slack notifications promptly
2. Act on duplicate defect alerts to reduce noise
3. Consider cancelling aging single-occurrence defects
4. Use ML tag suggestions to speed up triage
5. Monitor weekly dashboard reports for trends

### For Administrators
1. Keep credentials secure and rotate regularly
2. Monitor logs for authentication issues
3. Backup database weekly
4. Review ML model accuracy periodically
5. Update dependencies regularly

## 📞 Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify config: `config/config.yaml`
3. Check session: `/api/status`
4. Review this README
5. Check Slack notifications for system alerts

## 📄 License

Internal IBM tool - for authorized users only.

---

**Version**: 2.0.0  
**Last Updated**: April 2026  
**Maintained By**: Development Team

**Built with Flask, SQLite, scikit-learn, Playwright, and Docker**