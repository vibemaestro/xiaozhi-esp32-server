#!/bin/bash
# Script Author: @VanillaNahida
# This file is used to automatically download required files of this project and create all necessary directories
# Currently only supports X86 architecture Ubuntu systems, other systems are not tested

# Define interrupt handler function
handle_interrupt() {
    echo ""
    echo "Installation has been interrupted by user (Ctrl+C or Esc)"
    echo "If you want to reinstall, please run this script again"
    exit 1
}

# Set trap to handle Ctrl+C
trap handle_interrupt SIGINT

# Print colored ASCII art
echo -e "\e[1;32m"  # Set color to bright green
cat << "EOF"
Script Author: @Bilibili Vanilla-flavored Nahida Meow
 __      __            _  _  _            _   _         _      _      _        
 \ \    / /           (_)| || |          | \ | |       | |    (_)    | |       
  \ \  / /__ _  _ __   _ | || |  __ _    |  \| |  __ _ | |__   _   __| |  __ _ 
   \ \/ // _` || '_ \ | || || | / _` |   | . ` | / _` || '_ \ | | / _` | / _` |
    \  /| (_| || | | || || || || (_| |   | |\  || (_| || | | || || (_| || (_| |
     \/  \__,_||_| |_||_||_||_| \__,_|   |_| \_| \__,_||_| |_||_| \__,_| \__,_|                                                                                                                                                                                                                               
EOF
echo -e "\e[0m"  # Reset color
echo -e "\e[1;36m  Xiaozhi Server Full Deployment One-click Installation Script Ver 0.2 Updated 2025-08-20 \e[0m\n"
sleep 1



# Check and install whiptail
check_whiptail() {
    if ! command -v whiptail &> /dev/null; then
        echo "Installing whiptail..."
        apt update
        apt install -y whiptail
    fi
}

check_whiptail

# Create confirmation dialog
whiptail --title "Installation Confirmation" --yesno "Xiaozhi Server will be installed. Continue?" \
  --yes-button "Continue" --no-button "Exit" 10 50

# Execute action based on user selection
case $? in
  0)
    ;;
  1)
    exit 1
    ;;
esac

# Check root privilege
if [ $EUID -ne 0 ]; then
    whiptail --title "Permission Error" --msgbox "Please run this script with root privileges" 10 50
    exit 1
fi

# Check system version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" != "debian" ] && [ "$ID" != "ubuntu" ]; then
        whiptail --title "System Error" --msgbox "This script only supports Debian/Ubuntu systems" 10 60
        exit 1
    fi
else
    whiptail --title "System Error" --msgbox "Unable to determine system version, this script only supports Debian/Ubuntu systems" 10 60
    exit 1
fi

# Download config file function
check_and_download() {
    local filepath=$1
    local url=$2
    if [ ! -f "$filepath" ]; then
        if ! curl -fL --progress-bar "$url" -o "$filepath"; then
            whiptail --title "Error" --msgbox "Failed to download ${filepath}" 10 50
            exit 1
        fi
    else
        echo "${filepath} already exists, skipping download"
    fi
}

# Check if already installed
check_installed() {
    # Check if directory exists and is not empty
    if [ -d "/opt/xiaozhi-server/" ] && [ "$(ls -A /opt/xiaozhi-server/)" ]; then
        DIR_CHECK=1
    else
        DIR_CHECK=0
    fi
    
    # Check if container exists
    if docker inspect xiaozhi-esp32-server > /dev/null 2>&1; then
        CONTAINER_CHECK=1
    else
        CONTAINER_CHECK=0
    fi
    
    # Both checks pass
    if [ $DIR_CHECK -eq 1 ] && [ $CONTAINER_CHECK -eq 1 ]; then
        return 0  # Installed
    else
        return 1  # Not installed
    fi
}

# Upgrade related
if check_installed; then
    if whiptail --title "Already Installed" --yesno "Xiaozhi Server has been detected as installed. Do you want to upgrade?" 10 60; then
        # User chooses to upgrade, perform cleanup
        echo "Starting upgrade operation..."
        
        # Stop and remove all docker-compose services
        docker compose -f /opt/xiaozhi-server/docker-compose_all.yml down
        
        # Stop and remove specific containers (handle if they may not exist)
        containers=(
            "xiaozhi-esp32-server"
            "xiaozhi-esp32-server-web"
            "xiaozhi-esp32-server-db"
            "xiaozhi-esp32-server-redis"
        )
        
        for container in "${containers[@]}"; do
            if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
                docker stop "$container" >/dev/null 2>&1 && \
                docker rm "$container" >/dev/null 2>&1 && \
                echo "Successfully removed container: $container"
            else
                echo "Container does not exist, skipping: $container"
            fi
        done
        
        # Remove specific images (handle if they may not exist)
        images=(
            "thanhlcm90/xiaozhi-server:latest"
            "thanhlcm90/xiaozhi-server-web:latest"
        )
        
        for image in "${images[@]}"; do
            if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${image}$"; then
                docker rmi "$image" >/dev/null 2>&1 && \
                echo "Successfully removed image: $image"
            else
                echo "Image does not exist, skipping: $image"
            fi
        done
        
        echo "All cleanup operations complete"
        
        # Backup original config file
        mkdir -p /opt/xiaozhi-server/backup/
        if [ -f /opt/xiaozhi-server/data/.config.yaml ]; then
            cp /opt/xiaozhi-server/data/.config.yaml /opt/xiaozhi-server/backup/.config.yaml
            echo "Backed up original config file to /opt/xiaozhi-server/backup/.config.yaml"
        fi
        
        # Download the latest config files
        check_and_download "/opt/xiaozhi-server/docker-compose_all.yml" "https://ghfast.top/https://raw.githubusercontent.com/thanhlcm90/xiaozhi-esp32-server/refs/heads/main/deploy/docker-compose_all.yml"
        check_and_download "/opt/xiaozhi-server/nginx.conf" "https://ghfast.top/https://raw.githubusercontent.com/thanhlcm90/xiaozhi-esp32-server/refs/heads/main/deploy/nginx.conf"
        check_and_download "/opt/xiaozhi-server/data/.config.yaml" "https://ghfast.top/https://raw.githubusercontent.com/thanhlcm90/xiaozhi-esp32-server/refs/heads/main/deploy/config_from_api.yaml"
        
        # Start Docker services
        echo "Starting the latest version of services..."
        # Mark upgrade as completed to skip later download steps
        UPGRADE_COMPLETED=1
        docker compose -f /opt/xiaozhi-server/docker-compose_all.yml up -d
    else
          whiptail --title "Skip Upgrade" --msgbox "Upgrade cancelled, will continue to use current version." 10 50
          # Skip upgrade, continue with rest of install steps
    fi
fi


# Check for curl installation
if ! command -v curl &> /dev/null; then
    echo "------------------------------------------------------------"
    echo "curl not detected, installing..."
    apt update
    apt install -y curl
else
    echo "------------------------------------------------------------"
    echo "curl is already installed, skipping"
fi

# Check for Docker installation
if ! command -v docker &> /dev/null; then
    echo "------------------------------------------------------------"
    echo "Docker not detected, installing..."
    
    # Use domestic mirror instead of official source
    DISTRO=$(lsb_release -cs)
    MIRROR_URL="https://mirrors.aliyun.com/docker-ce/linux/ubuntu"
    GPG_URL="https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg"
    
    # Install base dependencies
    apt update
    apt install -y apt-transport-https ca-certificates curl software-properties-common gnupg
    
    # Create key directory and add domestic mirror key
    mkdir -p /etc/apt/keyrings
    curl -fsSL "$GPG_URL" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Add domestic mirror
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] $MIRROR_URL $DISTRO stable" \
        > /etc/apt/sources.list.d/docker.list
    
    # Add backup official key (in case domestic mirror's key fails)
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 7EA0A9C3F273FCD8 2>/dev/null || \
    echo "Warning: Some keys failed to be added, continue installation..."
    
    # Install Docker
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io
    
    # Start and enable Docker service
    systemctl start docker
    systemctl enable docker
    
    # Check if installation was successful
    if docker --version; then
        echo "------------------------------------------------------------"
        echo "Docker installation complete!"
    else
        whiptail --title "Error" --msgbox "Docker installation failed. Please check the log." 10 50
        exit 1
    fi
else
    echo "Docker is already installed, skipping"
fi

# Docker registry mirror configuration
MIRROR_OPTIONS=(
    "1" "Xuanyuan Mirror (Recommended)"
    "2" "Tencent Cloud Mirror"
    "3" "USTC Mirror"
    "4" "NetEase 163 Mirror"
    "5" "Huawei Cloud Mirror"
    "6" "Aliyun Mirror"
    "7" "Custom Mirror"
    "8" "Skip Configuration"
)

MIRROR_CHOICE=$(whiptail --title "Select Docker Mirror" --menu "Please select the Docker registry mirror to use" 20 60 10 \
"${MIRROR_OPTIONS[@]}" 3>&1 1>&2 2>&3) || {
    echo "User cancelled selection, exiting script"
    exit 1
}

case $MIRROR_CHOICE in
    1) MIRROR_URL="https://docker.xuanyuan.me" ;; 
    2) MIRROR_URL="https://mirror.ccs.tencentyun.com" ;; 
    3) MIRROR_URL="https://docker.mirrors.ustc.edu.cn" ;; 
    4) MIRROR_URL="https://hub-mirror.c.163.com" ;; 
    5) MIRROR_URL="https://05f073ad3c0010ea0f4bc00b7105ec20.mirror.swr.myhuaweicloud.com" ;; 
    6) MIRROR_URL="https://registry.aliyuncs.com" ;; 
    7) MIRROR_URL=$(whiptail --title "Custom Mirror" --inputbox "Please input the complete mirror URL:" 10 60 3>&1 1>&2 2>&3) ;; 
    8) MIRROR_URL="" ;; 
esac

if [ -n "$MIRROR_URL" ]; then
    mkdir -p /etc/docker
    if [ -f /etc/docker/daemon.json ]; then
        cp /etc/docker/daemon.json /etc/docker/daemon.json.bak
    fi
    cat > /etc/docker/daemon.json <<EOF
{
    "dns": ["8.8.8.8", "114.114.114.114"],
    "registry-mirrors": ["$MIRROR_URL"]
}
EOF
    whiptail --title "Configured Successfully" --msgbox "Mirror successfully added: $MIRROR_URL\nPress Enter to restart Docker service and continue..." 12 60
    echo "------------------------------------------------------------"
    echo "Restarting Docker service..."
    systemctl restart docker.service
fi

# Create installation directories
echo "------------------------------------------------------------"
echo "Creating installation directories..."
# Check and create data directory
if [ ! -d /opt/xiaozhi-server/data ]; then
    mkdir -p /opt/xiaozhi-server/data
    echo "Created data directory: /opt/xiaozhi-server/data"
else
    echo "Directory xiaozhi-server/data already exists, skipping"
fi

# Check and create model directory
if [ ! -d /opt/xiaozhi-server/models/SenseVoiceSmall ]; then
    mkdir -p /opt/xiaozhi-server/models/SenseVoiceSmall
    echo "Created model directory: /opt/xiaozhi-server/models/SenseVoiceSmall"
else
    echo "Directory xiaozhi-server/models/SenseVoiceSmall already exists, skipping"
fi

echo "------------------------------------------------------------"
echo "Starting voice recognition model download"
# Download model file
MODEL_PATH="/opt/xiaozhi-server/models/SenseVoiceSmall/model.pt"
if [ ! -f "$MODEL_PATH" ]; then
    (
    for i in {1..20}; do
        echo $((i*5))
        sleep 0.5
    done
    ) | whiptail --title "Downloading" --gauge "Downloading voice recognition model..." 10 60 0
    curl -fL --progress-bar https://modelscope.cn/models/iic/SenseVoiceSmall/resolve/master/model.pt -o "$MODEL_PATH" || {
        whiptail --title "Error" --msgbox "Failed to download model.pt file" 10 50
        exit 1
    }
else
    echo "model.pt file already exists, skipping download"
fi

# Only download if upgrade has not been completed
if [ -z "$UPGRADE_COMPLETED" ]; then
    check_and_download "/opt/xiaozhi-server/docker-compose_all.yml" "https://ghfast.top/https://raw.githubusercontent.com/thanhlcm90/xiaozhi-esp32-server/refs/heads/main/deploy/docker-compose_all.yml"
    check_and_download "/opt/xiaozhi-server/nginx.conf" "https://ghfast.top/https://raw.githubusercontent.com/thanhlcm90/xiaozhi-esp32-server/refs/heads/main/deploy/nginx.conf"
    check_and_download "/opt/xiaozhi-server/data/.config.yaml" "https://ghfast.top/https://raw.githubusercontent.com/thanhlcm90/xiaozhi-esp32-server/refs/heads/main/deploy/config_from_api.yaml"
fi

# Start Docker services
(
echo "------------------------------------------------------------"
echo "Pulling Docker images..."
echo "This may take several minutes. Please wait patiently."
docker compose -f /opt/xiaozhi-server/docker-compose_all.yml up -d

if [ $? -ne 0 ]; then
    whiptail --title "Error" --msgbox "Docker service failed to start, please try another registry mirror and re-execute this script." 10 60
    exit 1
fi

echo "------------------------------------------------------------"
echo "Checking service startup state..."
TIMEOUT=300
START_TIME=$(date +%s)
while true; do
    CURRENT_TIME=$(date +%s)
    if [ $((CURRENT_TIME - START_TIME)) -gt $TIMEOUT ]; then
        whiptail --title "Error" --msgbox "Service startup timed out, expected log not found within time limit." 10 60
        exit 1
    fi
    
    if docker logs xiaozhi-esp32-server-web 2>&1 | grep -q "Started AdminApplication in"; then
        break
    fi
    sleep 1
done

    echo "Server started successfully! Finalizing configuration..."
    echo "Starting service..."
    docker compose -f /opt/xiaozhi-server/docker-compose_all.yml up -d
    echo "Service started!"
)

# Secret key configuration

# Get public IP of the server
PUBLIC_IP=$(hostname -I | awk '{print $1}')
whiptail --title "Configure Server Secret Key" --msgbox "Please use your browser to open the following link, open the Smart Console and register an account: \n\nLocal address: http://127.0.0.1:8002/\nPublic address: http://$PUBLIC_IP:8002/ (If on cloud server, please open ports 8000/8001/8002 in security group).\n\nThe first user to register becomes the super admin. All later users are regular users. Regular users can only bind devices and configure agents; super admins can manage models, users, and parameters.\n\nAfter you finish registration, press Enter to continue." 18 70
SECRET_KEY=$(whiptail --title "Configure Server Secret Key" --inputbox "Log in the Smart Console with your super admin account\nLocal address: http://127.0.0.1:8002/\nPublic address: http://$PUBLIC_IP:8002/\nAt the top menu, go to Parameters Dictionary → Parameters Management, and find the parameter code: server.secret (server secret key).\nCopy the parameter value and paste it in the box below.\n\nPlease enter the secret key (leave blank to skip):" 15 60 3>&1 1>&2 2>&3)

if [ -n "$SECRET_KEY" ]; then
    python3 -c "
import sys, yaml; 
config_path = '/opt/xiaozhi-server/data/.config.yaml'; 
with open(config_path, 'r') as f: 
    config = yaml.safe_load(f) or {}; 
config['manager-api'] = {'url': 'http://xiaozhi-esp32-server-web:8002/xiaozhi', 'secret': '$SECRET_KEY'}; 
with open(config_path, 'w') as f: 
    yaml.dump(config, f); 
"
    docker restart xiaozhi-esp32-server
fi

# Get and display address info
LOCAL_IP=$(hostname -I | awk '{print $1}')

# Fix issue where the log file does not get ws address, use hardcoded address
whiptail --title "Installation Complete!" --msgbox "\
Service related addresses:\n\
Admin panel address: http://$LOCAL_IP:8002\n\
OTA Address: http://$LOCAL_IP:8002/xiaozhi/ota/\n\
Visual analysis API: http://$LOCAL_IP:8003/mcp/vision/explain\n\
WebSocket address: ws://$LOCAL_IP:8000/xiaozhi/v1/\n\
\nInstallation complete! Thank you for using.\nPress Enter to exit..." 16 70
