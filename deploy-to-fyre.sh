#!/bin/bash

# Deploy to Fyre VM Script
# This script creates all necessary files on the Fyre VM

echo "=========================================="
echo "Defect Monitor - Fyre VM Deployment"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Step 1: Installing Docker...${NC}"
cat << 'DOCKER_INSTALL'
apt-get update -y
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
docker --version
DOCKER_INSTALL

echo ""
echo -e "${BLUE}Step 2: Installing Docker Compose...${NC}"
cat << 'COMPOSE_INSTALL'
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
docker-compose --version
COMPOSE_INSTALL

echo ""
echo -e "${BLUE}Step 3: Creating project structure...${NC}"
cat << 'PROJECT_SETUP'
cd ~
mkdir -p defect-monitor-server/src
mkdir -p defect-monitor-server/config
mkdir -p defect-monitor-server/templates
mkdir -p defect-monitor-server/data
cd defect-monitor-server
PROJECT_SETUP

echo ""
echo -e "${BLUE}Step 4: Creating docker-compose.yml...${NC}"
cat << 'COMPOSE_FILE'
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
COMPOSE_FILE

echo ""
echo -e "${BLUE}Step 5: Creating Dockerfile...${NC}"
cat << 'DOCKERFILE'
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
DOCKERFILE

echo ""
echo -e "${BLUE}Step 6: Creating requirements.txt...${NC}"
cat << 'REQUIREMENTS'
cat > requirements.txt << 'EOF'
Flask==3.0.0
requests==2.31.0
APScheduler==3.10.4
PyYAML==6.0.1
EOF
REQUIREMENTS

echo ""
echo -e "${BLUE}Step 7: Creating .env file...${NC}"
cat << 'ENV_FILE'
cat > .env << 'EOF'
IBM_USERNAME=sweettypdevassy@ibm.com
IBM_PASSWORD=YOUR_PASSWORD_HERE
SLACK_WEBHOOK_URL=YOUR_SLACK_WEBHOOK_URL_HERE
EOF

echo ""
echo "IMPORTANT: Edit .env file with your credentials:"
echo "  vi .env"
echo "  Press 'i' to edit, ESC then ':wq' to save"
ENV_FILE

echo ""
echo -e "${GREEN}=========================================="
echo "Installation commands ready!"
echo "==========================================${NC}"
echo ""
echo "Copy the commands above and paste them into your Fyre VM console."
echo ""
echo "After running all commands, I'll provide the application files."

# Made with Bob
