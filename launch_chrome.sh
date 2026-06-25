#!/bin/bash
# Start Chrome with remote debugging for Playwright CDP connection
# Usage: ./launch_chrome.sh

CHROME=$(which google-chrome-stable || which google-chrome || which chromium-browser)

if [ -z "$CHROME" ]; then
    echo "Chrome not found!"
    exit 1
fi

# Kill existing Chrome if running
pkill -f "chrome.*remote-debugging" 2>/dev/null
sleep 1

# Start Chrome with remote debugging
"$CHROME" \
    --remote-debugging-port=9222 \
    --no-first-run \
    --no-default-browser-check \
    --user-data-dir="$HOME/.config/google-chrome/Default" \
    &
echo "Chrome started with remote debugging on port 9222"
echo "PID: $!"
