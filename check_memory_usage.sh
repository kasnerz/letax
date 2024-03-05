#!/bin/bash

# Set your memory limit in megabytes (MB)
MEMORY_LIMIT_MB=1500

while true; do
    # Get current timestamp
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    
    # Get current memory usage in kilobytes (KB)
    MEMORY_USAGE_KB=$(free -k | awk '/Mem/ {print $3}')
    
    # Convert KB to MB
    MEMORY_USAGE_MB=$((MEMORY_USAGE_KB / 1024))
    
    if [ $MEMORY_USAGE_MB -gt $MEMORY_LIMIT_MB ]; then
        echo "$TIMESTAMP - Memory usage is over the limit: $MEMORY_USAGE_MB MB. Rebooting..."
        killall -9 streamlit
        bash run.sh &
    else
        echo "$TIMESTAMP - Memory usage is within limits: $MEMORY_USAGE_MB MB."
    fi
    sleep 10
done





