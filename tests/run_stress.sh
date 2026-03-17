#!/bin/bash
# A script to stress test the Nginx server Rate limit and overall behavior

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "tmux not found. Install with: sudo apt install tmux"
    exit 1
fi

tmux new-session -d -s urlchecker-stress
tmux split-window -h -t urlchecker-stress
tmux select-pane -t 0
sleep 0.2
tmux split-window -v
sleep 0.2
tmux select-pane -t 2
sleep 0.2
tmux split-window -v
sleep 0.2

tmux send-keys -t urlchecker-stress:0.0 "stty -echo; date; stty echo" C-m
tmux send-keys -t urlchecker-stress:0.2 "stty -echo; date; stty echo" C-m

#tmux select-pane -t 1
tmux send-keys -t urlchecker-stress:0.1 "ssh -t urlchecker-test.restena.lu htop" C-m
#tmux select-pane -t 3
tmux send-keys -t urlchecker-stress:0.3 "ssh -t urlchecker-test.restena.lu bmon" C-m
#tmux select-pane -t 0
tmux send-keys -t urlchecker-stress:0.0 "date" C-m
tmux send-keys -t urlchecker-stress:0.0 "sleep 10" C-m
tmux send-keys -t urlchecker-stress:0.0 "ab -c 3 -n 24 https://urlchecker-test.restena.lu/main/all" C-m
#tmux select-pane -t 2
tmux send-keys -t urlchecker-stress:0.2 "date" C-m
tmux send-keys -t urlchecker-stress:0.2 "sleep 20" C-m
tmux send-keys -t urlchecker-stress:0.2 "ab -c 2 -n 1000 https://urlchecker-test.restena.lu/all" C-m
tmux send-keys -t urlchecker-stress:0.2 "echo 'Waiting for 2 minutes ...'" C-m
tmux send-keys -t urlchecker-stress:0.2 "sleep 120" C-m
tmux send-keys -t urlchecker-stress:0.2 "date" C-m
tmux send-keys -t urlchecker-stress:0.2 "ab -c 2 -n 10000 https://urlchecker-test.restena.lu/retests" C-m
tmux send-keys -t urlchecker-stress:0.2 "ab -c 10 -n 10000 https://urlchecker-test.restena.lu/sdssfds/fdedsf" C-m
tmux send-keys -t urlchecker-stress:0.2 "sleep 8" C-m
tmux send-keys -t urlchecker-stress:0.2 "ab -c 1 -t 50 https://urlchecker-test.restena.lu/fdsf454sf/1/one" C-m

# Attach to the session
echo "Starting tmux session 'urlchecker-stress'..."
date
echo "Controls:"
echo "  - Switch panes: Ctrl+B then arrow keys"
echo "  - Detach: Ctrl+B then D"
echo "  - Stop all: 'tmux kill-session -t urlchecker-stress'"
echo ""
sleep 1

tmux attach-session -t urlchecker-stress
# After detaching or session ending, wait and allow reattaching
while IFS= read -r -n 1 -t 0.1 _discard 2>/dev/null; do :; done  # flush stdin for first read command
while tmux has-session -t urlchecker-stress 2>/dev/null; do
    echo ""
    echo "Session 'urlchecker-stress' is running in background."
    echo "Press 'r' to reattach, 's' to stop, or 'q' to quit script (session keeps running): "
    read -n 1 -t 5 choice

    case $choice in
        r|R)
            echo ""
            echo "Reattaching..."
            tmux attach-session -t urlchecker-stress
            ;;
        s|S)
            echo ""
            echo "Stopping session..."
            tmux kill-session -t urlchecker-stress
            break
            ;;
        q|Q)
            echo ""
            echo "Exiting script. Session keeps running (tmux kill-session -t urlchecker-stress to stop)."
            exit 0
            ;;
        *)
            # Timeout or other key, just continue loop
            ;;
    esac
done

echo ""
echo "tmux session ended. All processes stopped."
