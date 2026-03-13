# Deployment Guide - Defect Monitor Server

Complete step-by-step guide to deploy the Defect Monitor Server on various platforms.

## 📋 Prerequisites

Before deployment, ensure you have:
- [ ] IBM W3ID credentials
- [ ] Slack webhook URL
- [ ] Server/VM with internet access
- [ ] Docker and Docker Compose installed (for Docker deployment)
- [ ] Python 3.9+ (for non-Docker deployment)

## 🚀 Deployment Options

### Option 1: Docker Deployment (Recommended)

#### Step 1: Prepare Server
```bash
# SSH into your server
ssh user@your-server-ip

# Install Docker (if not installed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

#### Step 2: Copy Project to Server
```bash
# On your local machine
cd /Users/sweettypdevassy/Desktop
tar -czf defect-monitor-server.tar.gz defect-monitor-server/

# Copy to server
scp defect-monitor-server.tar.gz user@your-server-ip:/home/user/

# On server
cd /home/user
tar -xzf defect-monitor-server.tar.gz
cd defect-monitor-server
```

#### Step 3: Configure
```bash
# Edit configuration
nano config/config.yaml

# Update these critical settings:
# - ibm.username
# - ibm.password
# - slack.webhook_url
# - components list
```

#### Step 4: Deploy
```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Test
curl http://localhost:5000/health
```

#### Step 5: Access Dashboard
```
http://your-server-ip:5000
```

---

### Option 2: Direct Python Deployment

#### Step 1: Prepare Server
```bash
# SSH into server
ssh user@your-server-ip

# Install Python 3.9+
sudo apt update
sudo apt install python3.9 python3-pip python3-venv -y

# Verify
python3 --version
```

#### Step 2: Setup Application
```bash
# Copy project to server (same as Docker option)
cd /home/user/defect-monitor-server

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 3: Configure
```bash
# Edit configuration
nano config/config.yaml
```

#### Step 4: Run Application
```bash
# Run directly (for testing)
python src/app.py

# Or use systemd for production (see below)
```

#### Step 5: Setup Systemd Service (Production)
```bash
# Create service file
sudo nano /etc/systemd/system/defect-monitor.service
```

Add this content:
```ini
[Unit]
Description=Defect Monitor Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/user/defect-monitor-server
Environment="PATH=/home/user/defect-monitor-server/venv/bin"
ExecStart=/home/user/defect-monitor-server/venv/bin/python src/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable defect-monitor
sudo systemctl start defect-monitor
sudo systemctl status defect-monitor

# View logs
sudo journalctl -u defect-monitor -f
```

---

### Option 3: IBM Cloud Deployment

#### Step 1: Install IBM Cloud CLI
```bash
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
ibmcloud login
```

#### Step 2: Create Container Registry
```bash
# Create namespace
ibmcloud cr namespace-add defect-monitor

# Build and push image
docker build -t us.icr.io/defect-monitor/defect-monitor-server:latest .
docker push us.icr.io/defect-monitor/defect-monitor-server:latest
```

#### Step 3: Deploy to Kubernetes
```bash
# Create deployment.yaml
cat > deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: defect-monitor
spec:
  replicas: 1
  selector:
    matchLabels:
      app: defect-monitor
  template:
    metadata:
      labels:
        app: defect-monitor
    spec:
      containers:
      - name: defect-monitor
        image: us.icr.io/defect-monitor/defect-monitor-server:latest
        ports:
        - containerPort: 5000
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: data
          mountPath: /app/data
      volumes:
      - name: config
        configMap:
          name: defect-monitor-config
      - name: data
        persistentVolumeClaim:
          claimName: defect-monitor-data
---
apiVersion: v1
kind: Service
metadata:
  name: defect-monitor
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 5000
  selector:
    app: defect-monitor
EOF

# Apply
kubectl apply -f deployment.yaml
```

---

### Option 4: AWS EC2 Deployment

#### Step 1: Launch EC2 Instance
```bash
# Launch Ubuntu 22.04 instance
# Instance type: t2.small or larger
# Security group: Allow port 5000 (or 80/443)
```

#### Step 2: Connect and Setup
```bash
# SSH to instance
ssh -i your-key.pem ubuntu@ec2-instance-ip

# Install Docker
sudo apt update
sudo apt install docker.io docker-compose -y
sudo usermod -aG docker ubuntu

# Logout and login again
exit
ssh -i your-key.pem ubuntu@ec2-instance-ip
```

#### Step 3: Deploy Application
```bash
# Copy project files
# Follow Docker deployment steps above

# Configure security group to allow port 5000
# Or setup nginx reverse proxy for port 80
```

---

## 🔧 Post-Deployment Configuration

### 1. Setup Nginx Reverse Proxy (Optional)

```bash
# Install nginx
sudo apt install nginx -y

# Create config
sudo nano /etc/nginx/sites-available/defect-monitor
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/defect-monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 2. Setup SSL with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

### 3. Setup Firewall

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 5000/tcp  # If accessing directly

# Enable firewall
sudo ufw enable
```

### 4. Setup Monitoring

```bash
# Install monitoring tools
sudo apt install htop iotop -y

# Setup log rotation
sudo nano /etc/logrotate.d/defect-monitor
```

Add:
```
/home/user/defect-monitor-server/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] Service is running: `docker-compose ps` or `systemctl status defect-monitor`
- [ ] Health check passes: `curl http://localhost:5000/health`
- [ ] Dashboard accessible: `http://your-server-ip:5000`
- [ ] IBM authentication works: Check `/api/status`
- [ ] Scheduled jobs configured: Check dashboard
- [ ] Slack notifications working: Trigger manual check
- [ ] Logs are being written: Check `logs/` directory
- [ ] Database created: Check `data/defects.db`

---

## 🔄 Maintenance Tasks

### Daily
- Check service status
- Review logs for errors
- Verify Slack notifications sent

### Weekly
- Review dashboard analytics
- Check disk space usage
- Verify scheduled jobs running

### Monthly
- Update dependencies
- Backup database
- Review and optimize configuration

---

## 📊 Monitoring Commands

```bash
# Check service status
docker-compose ps
# or
sudo systemctl status defect-monitor

# View logs
docker-compose logs -f
# or
sudo journalctl -u defect-monitor -f

# Check resource usage
docker stats
# or
htop

# Check disk space
df -h

# Check database size
du -sh data/

# Test API
curl http://localhost:5000/api/status | jq
```

---

## 🆘 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs

# Check configuration
cat config/config.yaml

# Verify ports
sudo netstat -tulpn | grep 5000

# Check permissions
ls -la data/ logs/
```

### Authentication Fails

```bash
# Verify credentials in config
grep -A 2 "ibm:" config/config.yaml

# Test IBM connectivity
curl -I https://libh-proxy1.fyre.ibm.com

# Check logs for auth errors
docker-compose logs | grep -i auth
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Restart service
docker-compose restart

# Check for memory leaks in logs
docker-compose logs | grep -i memory
```

---

## 🔐 Security Best Practices

1. **Use environment variables for secrets**
```bash
# Create .env file
cp .env.example .env
nano .env
```

2. **Restrict file permissions**
```bash
chmod 600 config/config.yaml
chmod 700 data/ logs/
```

3. **Use firewall**
```bash
sudo ufw enable
sudo ufw allow from trusted-ip to any port 5000
```

4. **Regular updates**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker-compose pull
docker-compose up -d
```

5. **Backup regularly**
```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf backup-$DATE.tar.gz data/ config/
```

---

## 📞 Support

If you encounter issues:
1. Check logs: `docker-compose logs -f`
2. Verify configuration
3. Test connectivity to IBM systems
4. Review this deployment guide
5. Check README.md for troubleshooting

---

**Deployment Guide Version**: 1.0.0  
**Last Updated**: March 2026