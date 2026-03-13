# Defect Monitor Server

A production-ready, server-based solution for automated IBM Liberty defect monitoring that runs 24/7 independently of your laptop.

## 🎯 Why This Solution?

### Chrome Extension Limitations ❌
- ❌ Requires laptop to be running
- ❌ Dashboard only visible to you
- ❌ Single point of failure
- ❌ No team collaboration
- ❌ Session management issues

### Server Solution Benefits ✅
- ✅ **24/7 Availability** - Runs independently on server
- ✅ **Team-Wide Access** - Web dashboard accessible to everyone
- ✅ **Reliable** - No dependency on individual laptops
- ✅ **Scalable** - Easy to add more components/teams
- ✅ **Professional** - Production-ready with monitoring
- ✅ **Automated** - Scheduled checks and notifications

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Defect Monitor Server                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   IBM Auth   │  │    Defect    │  │    Slack     │      │
│  │   Module     │→ │   Checker    │→ │  Notifier    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                  ↓                  ↓              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Scheduler   │  │   Database   │  │     Flask    │      │
│  │  (APScheduler)│  │  (SQLite)    │  │   Dashboard  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ↓                    ↓                    ↓
    IBM APIs            Historical Data      Team Dashboard
```

## 📦 What's Included

### Core Components
- **IBM Authentication** (`ibm_auth.py`) - Handles W3ID login and session management
- **Defect Checker** (`defect_checker.py`) - Fetches and processes defects from IBM systems
- **Slack Notifier** (`slack_notifier.py`) - Sends formatted notifications to Slack channels
- **Database** (`database.py`) - SQLite database for historical tracking
- **Scheduler** (`scheduler.py`) - APScheduler for automated daily/weekly tasks
- **Flask App** (`app.py`) - Web dashboard and REST API

### Web Dashboard
- Real-time defect status
- 7-day trend analysis with charts
- Component-wise breakdown
- Historical data visualization
- Accessible to entire team via browser

### Docker Support
- Containerized application
- Easy deployment with docker-compose
- Portable across any server/cloud

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- IBM W3ID credentials
- Slack webhook URL
- Server/VM with internet access

### Installation

1. **Clone/Copy the project**
```bash
cd /path/to/server
# Copy the defect-monitor-server folder
```

2. **Configure settings**
```bash
cd defect-monitor-server

# Edit config/config.yaml with your settings
nano config/config.yaml
```

Update these key settings:
```yaml
ibm:
  username: "your.email@ibm.com"
  password: "your_password"

slack:
  webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  channel: "#defect-notifications"

components:
  - name: "JCA"
    slack_channel: "#jca-defects"
  - name: "JPA"
    slack_channel: "#jpa-defects"
  # Add more components...

schedule:
  daily_check_time: "10:00"  # 10 AM IST
  weekly_dashboard_day: "monday"
  weekly_dashboard_time: "11:00"
```

3. **Build and run with Docker**
```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f
```

4. **Access the dashboard**
```
http://your-server-ip:5000
```

## 📊 Usage

### Web Dashboard
- **Home Page**: `http://server:5000/` - System status and quick actions
- **Dashboard**: `http://server:5000/dashboard` - 7-day analytics and charts

### API Endpoints
- `GET /api/status` - System status and session info
- `GET /api/weekly-data?days=7` - Get weekly data
- `GET /api/latest-snapshot` - Get latest defect snapshot
- `POST /api/check-now` - Trigger manual check
- `POST /api/refresh-session` - Refresh IBM session
- `GET /health` - Health check endpoint

### Automated Tasks
- **Daily Check**: Runs at configured time (default 10:00 AM IST)
- **Weekly Dashboard**: Generates every Monday at 11:00 AM IST
- **Session Refresh**: Every 2 hours
- **Data Cleanup**: Weekly (keeps 90 days of data)

## 🔧 Configuration

### Component Configuration
Add/remove components in `config/config.yaml`:
```yaml
components:
  - name: "Component Name"
    slack_channel: "#channel-name"
```

### Schedule Configuration
```yaml
schedule:
  daily_check_time: "10:00"  # HH:MM format (IST)
  weekly_dashboard_day: "monday"
  weekly_dashboard_time: "11:00"
  timezone: "Asia/Kolkata"
```

### Notification Rules
```yaml
notifications:
  send_on_no_defects: false  # Send even if no defects
  group_by_component: true
  include_soe_defects: true
  max_defects_per_notification: 50
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
docker-compose restart

# Rebuild after code changes
docker-compose build
docker-compose up -d

# Check status
docker-compose ps

# Execute command in container
docker-compose exec defect-monitor python -c "print('Hello')"
```

## 📁 Project Structure

```
defect-monitor-server/
├── src/
│   ├── app.py              # Main Flask application
│   ├── ibm_auth.py         # IBM authentication
│   ├── defect_checker.py   # Defect fetching logic
│   ├── slack_notifier.py   # Slack notifications
│   ├── database.py         # Database operations
│   └── scheduler.py        # Task scheduling
├── templates/
│   ├── index.html          # Home page
│   └── dashboard.html      # Dashboard page
├── config/
│   └── config.yaml         # Configuration file
├── data/                   # Database files (auto-created)
├── logs/                   # Log files (auto-created)
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose config
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔒 Security

- Credentials stored in config file (not in code)
- Use environment variables for sensitive data in production
- Database stored locally in container
- No external data transmission except to IBM and Slack
- HTTPS recommended for production deployment

## 🚀 Deployment Options

### Option 1: Docker on VM (Recommended)
```bash
# On your server/VM
docker-compose up -d
```

### Option 2: IBM Cloud
```bash
# Deploy to IBM Cloud Kubernetes
kubectl apply -f k8s-deployment.yaml
```

### Option 3: AWS EC2
```bash
# Launch EC2 instance
# Install Docker
# Clone repo and run docker-compose
```

### Option 4: Azure VM
```bash
# Create Azure VM
# Install Docker
# Deploy with docker-compose
```

## 📈 Monitoring

### Health Check
```bash
curl http://localhost:5000/health
```

### View Logs
```bash
# Container logs
docker-compose logs -f

# Application logs
tail -f logs/defect_monitor.log
```

### Check Scheduled Jobs
Access the dashboard at `http://server:5000/api/status` to see next run times.

## 🔄 Maintenance

### Update Configuration
```bash
# Edit config
nano config/config.yaml

# Restart service
docker-compose restart
```

### Backup Database
```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/
```

### Update Application
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d
```

## 🆘 Troubleshooting

### Service Won't Start
```bash
# Check logs
docker-compose logs

# Check configuration
cat config/config.yaml

# Verify ports are available
netstat -tulpn | grep 5000
```

### Authentication Issues
```bash
# Check IBM credentials in config
# Verify VPN/network access to IBM systems
# Check logs for authentication errors
docker-compose logs | grep -i auth
```

### No Slack Notifications
```bash
# Verify webhook URL in config
# Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test"}' \
  YOUR_WEBHOOK_URL

# Check logs
docker-compose logs | grep -i slack
```

### Dashboard Not Loading
```bash
# Check if service is running
docker-compose ps

# Check port mapping
docker-compose port defect-monitor 5000

# Access logs
docker-compose logs -f
```

## 📞 Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify configuration: `config/config.yaml`
3. Check IBM session: Visit `/api/status`
4. Review this README

## 🎓 Migration from Chrome Extension

### Step 1: Export Extension Data
Your Chrome extension data is local. The server will start fresh.

### Step 2: Configure Server
Use the same settings from your extension in `config/config.yaml`.

### Step 3: Test
Run a manual check to verify everything works.

### Step 4: Inform Team
Share the dashboard URL with your team.

### Step 5: Decommission Extension
Once server is stable, you can stop using the Chrome extension.

## 📝 Advantages Over Extension

| Feature | Chrome Extension | Server Solution |
|---------|-----------------|-----------------|
| **Availability** | Only when laptop on | 24/7 |
| **Team Access** | Single user | Everyone |
| **Reliability** | Depends on you | Independent |
| **Dashboard** | Local only | Web-based |
| **Scalability** | Limited | Unlimited |
| **Maintenance** | Manual | Automated |
| **Monitoring** | Basic | Full logging |
| **Backup** | None | Automated |

## 🔮 Future Enhancements

- [ ] Email notifications
- [ ] Multiple Slack workspaces
- [ ] User authentication for dashboard
- [ ] Advanced analytics and reporting
- [ ] Integration with Jira/GitHub
- [ ] Mobile app
- [ ] Alert rules customization
- [ ] Multi-tenant support

## 📄 License

Internal IBM tool - for authorized users only.

## 🙏 Acknowledgments

Built to replace the Chrome extension and provide a robust, team-wide solution for defect monitoring.

---

**Version**: 1.0.0  
**Last Updated**: March 2026  
**Maintained By**: Development Team