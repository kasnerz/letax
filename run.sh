#!/bin/bash

# Script for launching the main app
# The first argument may contain a *total* memory limit in MB (including all other apps)
# The script automatically re-launches the app if memory usage exceeds a given limit


# Set VERBOSE if we got -v
if [[ "$1" == "-v" ]]; then
    VERBOSE=1
    shift
fi

# Set the memory limit in MB
# The limit should be something like 500 MB less than the total memory available, i.e. 1500 MB for 2GB instance
MEMORY_LIMIT_MB=${1:-0} # 0 means no limit, default
REFRESH_RATE=5 # seconds

CMD="streamlit run \"src/app/0_🪧_Hlavní stránka.py\""

# If memory limit is unset, do not check memory usage
if [ $MEMORY_LIMIT_MB -eq 0 ]; then
    echo "Memory limit is not set, app will be launched directly."
    eval $CMD
else
    echo "Memory limit is set to $MEMORY_LIMIT_MB MB."
    echo "Running app in the background..."
    eval $CMD &
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
            eval $CMD &
        else
            if [ $VERBOSE ]; then
                echo "$TIMESTAMP - Memory usage is within limits: $MEMORY_USAGE_MB MB."
            fi
        fi
        sleep $REFRESH_RATE
    done
fi

