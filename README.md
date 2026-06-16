## Featured example: VDA5050 → TurtleBot3 coffee delivery

A full end-to-end demo: a master sends multi-node coffee orders, and a
simulated TurtleBot3 navigates with Nav2, picks up the coffee, delivers it,
and returns to base (one order at a time).

**Full guide (how it works, customizing, troubleshooting):**
[`vda5050_core_py/turtlebot3/ReadMe.md`](vda5050_core_py/turtlebot3/ReadMe.md)

### Quick start

**Prerequisites:** ROS 2 Jazzy + Gazebo (gz), `turtlebot3_gazebo`,
`turtlebot3_navigation2`, `nav2_simple_commander`, `mosquitto`, `paho-mqtt`. The
demo map of `turtlebot3_house` is bundled at
`vda5050_core_py/turtlebot3/maps/`.

**Build once:**

```bash
cd ~/vda5050_core
colcon build --symlink-install
source install/setup.bash
```

**Run (5 terminals)**

```bash
# Terminal 1 - Gazebo simulation
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo turtlebot3_house.launch.py

# Terminal 2 - Nav2 + AMCL with the saved map
# Then in RViz click "2D Pose Estimate" at the robot's real location.
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
    use_sim_time:=True \
    map:=$HOME/vda5050_core/vda5050_core_py/turtlebot3/maps/house_office_map.yaml

# Terminal 3 - MQTT broker
mosquitto -p 1883

# Terminal 4 - AGV client (waits for Nav2, then for orders)
source ~/vda5050_core/install/setup.bash
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 example_turtlebot3_client.py

# Terminal 5 - Master (publishes the coffee orders)
source ~/vda5050_core/install/setup.bash
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 publish_turtlebot3_route.py
```
**Notes**

> Nothing drives until you set the **2D Pose Estimate** in RViz so AMCL
> localizes. See the full guide for expected output and troubleshooting.
