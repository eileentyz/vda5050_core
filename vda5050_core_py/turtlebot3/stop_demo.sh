#!/usr/bin/env bash
#
# Stop the VDA5050 -> TurtleBot3 demo cleanly.
#
# This stops the tmux session and kills leftover Gazebo processes that may
# continue running after the tmux panes are closed.
#
# Usage:
#   ./stop_demo.sh
#
set -uo pipefail

SESSION="${SESSION:-tb3demo}"

if tmux kill-session -t "$SESSION" 2>/dev/null; then
  echo "killed tmux session '$SESSION'"
else
  echo "no tmux session '$SESSION' (already stopped?)"
fi

killed_any=false
for pat in 'turtlebot3_house.world' 'gz sim -g'; do
  if pkill -f "$pat" 2>/dev/null; then
    echo "killed Gazebo: $pat"
    killed_any=true
  fi
done
$killed_any || echo "no Gazebo processes matched"

echo "done."
