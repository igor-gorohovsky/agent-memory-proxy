#!/bin/bash

set -e

check_python_version() {
    if ! command -v python3 &>/dev/null; then
        echo "❌ Error: Python 3 is not installed"
        exit 1
    fi
    
    local python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local required_major=3
    local required_minor=8
    
    IFS='.' read -r major minor <<< "$python_version"
    
    if [ "$major" -lt "$required_major" ] || ([ "$major" -eq "$required_major" ] && [ "$minor" -lt "$required_minor" ]); then
        echo "❌ Error: Python ${required_major}.${required_minor} or higher is required (found $python_version)"
        exit 1
    fi
    
    echo "✓ Python $python_version detected"
}

install_dependencies() {
    if command -v uv &> /dev/null; then
        echo "✓ uv is installed"
        echo "Installing dependencies with uv..."
        uv sync
    else
        echo "⚠️  uv not found. Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Add uv to PATH for current session
        export PATH="$HOME/.cargo/bin:$PATH"
        
        if command -v uv &> /dev/null; then
            echo "✓ uv installed successfully"
            echo "Installing dependencies with uv..."
            uv sync
        else
            echo "❌ Failed to install uv. Please install manually: https://github.com/astral-sh/uv"
            exit 1
        fi
    fi
}

# Get the actual script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==================================="
echo "Agent Memory Proxy Installation"
echo "==================================="

check_python_version
install_dependencies

# Create directories if needed
mkdir -p ~/.config/agent-memory-proxy

# Check we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ Error: This installer only supports Linux/Ubuntu"
    exit 1
fi

echo "✓ Running on Linux"

# Offer to install as service
read -p "Would you like to install as a systemd service? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create systemd service
    SERVICE_FILE="/etc/systemd/system/agent-memory-proxy.service"
    echo "Creating systemd service..."
    
    # Check if service template exists
    if [ ! -f "$PROJECT_DIR/scripts/daemons/agent-memory-proxy.service" ]; then
        echo "❌ Error: Service template not found at $PROJECT_DIR/scripts/daemons/agent-memory-proxy.service"
        exit 1
    fi
    
    # Copy template and replace placeholders using mktemp
    SERVICE_TEMP=$(mktemp)
    sed -e "s|%USER%|$USER|g" \
        -e "s|%HOME%|$HOME|g" \
        -e "s|%WORKING_DIR%|$PROJECT_DIR|g" \
        "$PROJECT_DIR/scripts/daemons/agent-memory-proxy.service" > "$SERVICE_TEMP"
    
    sudo mv "$SERVICE_TEMP" "$SERVICE_FILE"
    if ! sudo systemctl daemon-reload 2>/dev/null; then
        echo "⚠️  Warning: Failed to reload systemd daemon"
    fi
    if ! sudo systemctl enable agent-memory-proxy 2>/dev/null; then
        echo "⚠️  Warning: Failed to enable service"
    fi
    echo "✓ Systemd service installed"
    echo "To start: sudo systemctl start agent-memory-proxy"
fi

echo
echo "==================================="
echo "✓ Installation complete!"
echo "==================================="
echo
echo "Next steps:"
echo "1. Set AGENT_MEMORY_PATHS environment variable"
echo "2. Create .amp.yaml in your projects"
echo "3. Run: uv run amp"
echo
echo "See README.md for detailed instructions"
