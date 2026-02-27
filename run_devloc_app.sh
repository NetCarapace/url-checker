#!/bin/bash

# Function to cleanup processes on exit
cleanup() {
    echo "Shutting down processes..."
    kill $CELERY_PID 2>/dev/null
    kill $FLASK_PID 2>/dev/null
    wait $CELERY_PID 2>/dev/null
    wait $FLASK_PID 2>/dev/null
    echo "All processes terminated."
    exit 0
}

if [ "${FLASK_DEBUG}" = "True" ]; then
    # tmux is a good trick if we want to be able to run debugger in interactive mode
    # Check if tmux is installed
    if ! command -v tmux &> /dev/null; then
        echo "tmux not found. Install with: sudo apt install tmux"
        exit 1
    fi

    tmux new-session -d -s urlchecker
    tmux split-window -h -t urlchecker
    tmux select-pane -t 0
    tmux split-window -v

    # Celery worker
    tmux send-keys -t urlchecker:0.2 "cd src && uv run celery -A url_checker.app.celery_app worker --loglevel=info" C-m

    # Flask app
    tmux send-keys -t urlchecker:0.1 "uv run flask run" C-m

    # Attach to the session
    echo "Starting tmux session 'urlchecker'..."
    echo "Controls:"
    echo "  - Switch panes: Ctrl+B then arrow keys"
    echo "  - Detach: Ctrl+B then D"
    echo "  - Stop all: 'tmux kill-session -t urlchecker'"
    echo ""
    sleep 1

    tmux attach-session -t urlchecker
    # After detaching or session ending, wait and allow reattaching
    while tmux has-session -t urlchecker 2>/dev/null; do
        echo ""
        echo "Session 'urlchecker' is running in background."
        echo "Press 'r' to reattach, 's' to stop, or 'q' to quit script (session keeps running): "
        read -n 1 -t 5 choice

        case $choice in
            r|R)
                echo ""
                echo "Reattaching..."
                tmux attach-session -t urlchecker
                ;;
            s|S)
                echo ""
                echo "Stopping session..."
                tmux kill-session -t urlchecker
                break
                ;;
            *)
                # Timeout or other key, just continue loop
                ;;
        esac
    done

    echo ""
    echo "tmux session ended. All processes stopped."

else
    # Simulate prod -> no breakpoint possible
    trap cleanup SIGINT SIGTERM

    echo "Starting Celery worker..."
    uv run celery -A url_checker.celery_config.celery_app worker --loglevel=info &
    CELERY_PID=$!

    echo "Celery PID: $CELERY_PID"

    # Run Flask in background for normal operation
    echo "Starting Flask app..."
    uv run flask run &
    FLASK_PID=$!

    echo "Flask PID: $FLASK_PID"
    echo "Press Ctrl+C to stop both processes"

    # Wait for both processes
    wait $CELERY_PID $FLASK_PID
fi
