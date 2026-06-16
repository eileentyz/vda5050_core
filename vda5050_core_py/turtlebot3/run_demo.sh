#!/usr/bin/env bash
#
# Launch the full VDA5050 -> TurtleBot3 coffee-delivery demo in one tmux session.
#
# Windows: sim | nav2 | broker | vda5050
#
# The vda5050 window is split into two panes:
#   left  = AGV client
#   right = master/order publisher
#
# Because Nav2 needs a manual "2D Pose Estimate" in RViz, the master is NOT
# started automatically. Its pane pre-types the command and waits for you to
# press Enter once the robot is localized and the client is ready.
#
# Usage:
#   ./run_demo.sh
#
set -euo pipefail

SESSION="${SESSION:-tb3demo}"
WS="${VDA5050_WS:-$HOME/vda5050_core}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
BROKER_PORT="${BROKER_PORT:-1883}"
MODEL="${TURTLEBOT3_MODEL:-burger}"

DEMO_DIR="$WS/vda5050_core_py/turtlebot3"
MAP="$DEMO_DIR/maps/house_office_map.yaml"

# Sanity checks
command -v tmux >/dev/null 2>&1 || { echo "tmux not found: sudo apt install tmux"; exit 1; }
command -v mosquitto >/dev/null 2>&1 || { echo "mosquitto not found: sudo apt install mosquitto"; exit 1; }

[ -f "$ROS_SETUP" ]            || { echo "ROS setup not found: $ROS_SETUP (set ROS_SETUP=...)"; exit 1; }
[ -f "$WS/install/setup.bash" ] || { echo "workspace not built: run 'colcon build' in $WS"; exit 1; }
[ -f "$MAP" ]                  || { echo "map not found: $MAP"; exit 1; }

# Sourced at the top of every ROS window.
ENV="source $ROS_SETUP; source $WS/install/setup.bash; export TURTLEBOT3_MODEL=$MODEL;"

# Fresh session
# Kill a previous session AND any Gazebo it orphaned.
# gz sim can sometimes survive after the tmux session is killed, so clean it up.
tmux kill-session -t "$SESSION" 2>/dev/null || true
pkill -f 'turtlebot3_house.world' 2>/dev/null || true
pkill -f 'gz sim -g' 2>/dev/null || true

tmux new-session -d -s "$SESSION" -n sim

# 1. Gazebo simulation
tmux send-keys -t "$SESSION:sim" \
  "$ENV ros2 launch turtlebot3_gazebo turtlebot3_house.launch.py" C-m

# 2. Nav2 + AMCL with the bundled map
# Wait a bit for the simulation to come up first.
tmux new-window -t "$SESSION" -n nav2
tmux send-keys -t "$SESSION:nav2" \
  "$ENV sleep 6; ros2 launch turtlebot3_navigation2 navigation2.launch.py use_sim_time:=True map:=$MAP" C-m

# 3. MQTT broker
tmux new-window -t "$SESSION" -n broker
tmux send-keys -t "$SESSION:broker" \
  "mosquitto -p $BROKER_PORT" C-m

# 4 + 5. Client and master share one window so you can watch the
#        order/response conversation side-by-side.
tmux new-window -t "$SESSION" -n vda5050

# Left pane: AGV client
# The client waits internally for Nav2 to become active.
tmux send-keys -t "$SESSION:vda5050.0" \
  "$ENV sleep 10; cd $DEMO_DIR; python3 example_turtlebot3_client.py" C-m

# Right pane: master/order publisher
# The command is pre-typed but NOT executed yet.
tmux split-window -h -t "$SESSION:vda5050"
tmux send-keys -t "$SESSION:vda5050.1" \
  "$ENV cd $DEMO_DIR; echo; echo '>>> Set the 2D Pose Estimate in RViz, wait for the client left pane to print [tb3] runtime started, THEN press Enter here to publish orders <<<'; echo" C-m

# Type the master command but leave it for the user to run.
# No C-m here, so it will not execute automatically.
tmux send-keys -t "$SESSION:vda5050.1" \
  "python3 publish_turtlebot3_route.py"

# Land on the vda5050 window with the master pane focused.
tmux select-window -t "$SESSION:vda5050"
tmux select-pane -t "$SESSION:vda5050.1"

echo "Started tmux session '$SESSION'."
echo "  Windows:"
echo "    0: sim"
echo "    1: nav2"
echo "    2: broker"
echo "    3: vda5050 [left: client | right: master]"
echo
echo "  Switch windows: Ctrl-b then 0/1/2/3, or Ctrl-b then w"
echo "  Switch panes:   Ctrl-b then o, or Ctrl-b then arrow key"
echo "  Stop demo:      ./stop_demo.sh"
echo

# Attach, unless already inside tmux.
if [ -z "${TMUX:-}" ]; then
  tmux attach -t "$SESSION"
else
  echo "Already inside tmux — attach from a plain shell with:"
  echo "  tmux attach -t $SESSION"
fi