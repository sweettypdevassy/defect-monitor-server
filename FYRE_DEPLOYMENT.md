# Fyre VM Deployment Guide

## Quick Deployment Steps

Copy and paste these commands in your Fyre VM console terminal.

### Step 1: Install Docker

```bash
# Update system
apt-get update -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verify
docker --version
```

### Step 2: Install Docker Compose

```bash
# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make executable
chmod +x /usr/local/bin/docker-compose

# Verify
docker-compose --version
```

### Step 3: Install Git

```bash
apt-get install -y git
```

### Step 4: Clone or Create Project

**Option A: If you have Git repo**
```bash
cd ~
git clone https://github.com/your-username/defect-monitor-server.git
cd defect-monitor-server
```

**Option B: Create manually**
```bash
cd ~
mkdir -p defect-monitor-server
cd defect-monitor-server
mkdir -p src config templates data
```

### Step 5: Create Configuration Files

Run these commands to create all necessary files:

#### Create docker-compose.yml
```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  defect-monitor:
    build: .
    container_name: defect-monitor-server
    ports:
      - "5001:5000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    env_file:
      - .env
    restart: unless-stopped
    environment:
      - TZ=Asia/Calcutta
EOF
```

#### Create Dockerfile
```bash
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY templates/ ./templates/
COPY config/ ./config/

RUN mkdir -p /app/data

EXPOSE 5000

CMD ["python", "src/app.py"]
EOF
```

#### Create requirements.txt
```bash
cat > requirements.txt << 'EOF'
Flask==3.0.0
requests==2.31.0
APScheduler==3.10.4
PyYAML==6.0.1
EOF
```

#### Create .env file
```bash
cat > .env << 'EOF'
IBM_USERNAME=sweettypdevassy@ibm.com
IBM_PASSWORD=YOUR_PASSWORD_HERE
SLACK_WEBHOOK_URL=YOUR_SLACK_WEBHOOK_URL_HERE
EOF
```

**IMPORTANT: Edit .env with your actual credentials:**
```bash
vi .env
# Press 'i' to edit
# Update IBM_PASSWORD and SLACK_WEBHOOK_URL
# Press ESC, then type :wq to save
```

### Step 6: Transfer Application Files

Since you have the complete application on your laptop, use SCP to transfer:

**On your laptop (in a new terminal):**
```bash
cd /Users/sweettypdevassy/Desktop
tar -czf defect-monitor-files.tar.gz defect-monitor-server/src defect-monitor-server/config defect-monitor-server/templates

# If you can SSH (via VPN):
scp defect-monitor-files.tar.gz root@10.15.246.236:~/

# If SSH doesn't work, we'll create files manually
```

**On Fyre VM:**
```bash
cd ~/defect-monitor-server
tar -xzf ~/defect-monitor-files.tar.gz --strip-components=1
```

### Step 7: Build and Start

```bash
cd ~/defect-monitor-server

# Build Docker image
docker-compose build

# Start service
docker-compose up -d

# Check status
docker ps

# View logs
docker logs -f defect-monitor-server
```

### Step 8: Test Authentication

```bash
# Watch logs for authentication
docker logs defect-monitor-server | grep -i "auth"

# Look for:
# ✅ "Authentication successful" → MFA bypassed!
# ❌ "Authentication failed: 401" → Still has MFA issue
```

### Step 9: Access Dashboard

```bash
# Get VM IP
hostname -I

# Access from browser (if on IBM VPN):
# http://10.15.246.236:5001/dashboard
```

## Troubleshooting

### If Docker build fails
```bash
# Check Docker service
systemctl status docker

# Restart Docker
systemctl restart docker
```

### If authentication fails
```bash
# Check logs
docker logs defect-monitor-server

# Check environment variables
docker exec defect-monitor-server env | grep IBM
```

### If port is blocked
```bash
# Check if port is open
netstat -tulpn | grep 5001

# Try different port in docker-compose.yml
# Change "5001:5000" to "8080:5000"
```

## Next Steps After Successful Deployment

1. Share dashboard URL with team
2. Monitor logs for a few days
3. Adjust schedule times if needed
4. Set up automated backups
5. Document for team

## Important Notes

- Console session expires after 20 minutes
- Use `screen` or `tmux` for long-running commands
- Check logs regularly: `docker logs -f defect-monitor-server`
- Restart service: `docker-compose restart`
- Stop service: `docker-compose down`