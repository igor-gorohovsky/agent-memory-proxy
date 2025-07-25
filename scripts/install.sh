#!/bin/bash
# Agent Memory Proxy - Installation Script for Unix-like systems

set -e

echo "==================================="
echo "Agent Memory Proxy Installation"
echo "==================================="

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "❌ Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi

echo "✓ Python $python_version detected"

# Check if Poetry is installed
if command -v poetry &> /dev/null; then
    echo "✓ Poetry is installed"
    echo "Installing dependencies with Poetry..."
    poetry install
else
    echo "⚠️  Poetry not found. Installing dependencies with pip..."
    pip3 install .

# Create directories if needed
mkdir -p ~/.config/agent-memory-proxy

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
fi

echo "✓ Detected OS: $OS"

# Offer to install as service
read -p "Would you like to install as a background service? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    case $OS in
        linux)
            # Create systemd service
            SERVICE_FILE="/etc/systemd/system/agent-memory-proxy.service"
            echo "Creating systemd service..."
            
            cat > /tmp/agent-memory-proxy.service << EOF
[Unit]
Description=Agent Memory Proxy
After=network.target

[Service]
Type=simple
User=$USER
Environment="AGENT_MEMORY_PATHS=$HOME/projects"
ExecStart=$(which python3) $(pwd)/src/main.py
Restart=always
WorkingDirectory=$(pwd)

[Install]
WantedBy=multi-user.target
EOF
            
            sudo mv /tmp/agent-memory-proxy.service $SERVICE_FILE
            sudo systemctl daemon-reload
            sudo systemctl enable agent-memory-proxy
            echo "✓ Systemd service installed"
            echo "To start: sudo systemctl start agent-memory-proxy"
            ;;
            
        macos)
            # Create launchd plist
            PLIST_FILE="$HOME/Library/LaunchAgents/com.agent-memory-proxy.plist"
            echo "Creating launchd service..."
            
            cat > $PLIST_FILE << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.agent-memory-proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>$(pwd)/src/main.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>AGENT_MEMORY_PATHS</key>
        <string>$HOME/projects</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>$(pwd)</string>
</dict>
</plist>
EOF
            
            launchctl load $PLIST_FILE
            echo "✓ Launchd service installed"
            echo "Service will start automatically on login"
            ;;
            
        *)
            echo "⚠️  Automatic service installation not supported for this OS"
            echo "Please refer to the README for manual setup instructions"
            ;;
    esac
fi

echo
echo "==================================="
echo "✓ Installation complete!"
echo "==================================="
echo
echo "Next steps:"
echo "1. Set AGENT_MEMORY_PATHS environment variable"
echo "2. Create .amp.yaml in your projects"
echo "3. Run: python3 src/main.py"
echo
echo "See README.md for detailed instructions"
