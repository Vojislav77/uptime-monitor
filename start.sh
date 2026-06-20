#!/bin/bash

# --------------------------------------------
# Uptime Monitor Launcher
# --------------------------------------------

# 1. Check if the virtual environment exists
if [ ! -d "venv" ]; then
    echo "🔧 First run detected. Setting up virtual environment..."
    python3 -m venv venv
    echo "📦 Installing dependencies (flask, requests)..."
    venv/bin/pip install requests flask > /dev/null
    echo "✅ Setup complete!"
fi

# 2. Open the dashboard in your default browser (optional, but nice!)
# Wait 2 seconds for the server to start, then open the browser
(sleep 2 && xdg-open http://localhost:5000) &

# 3. Start the monitor using the virtual environment's Python
echo "🚀 Starting Uptime Monitor..."
venv/bin/python uptime_monitor.py