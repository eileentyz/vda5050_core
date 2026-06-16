# VDA5050 Library and Support Tools

C++ libraries and tools for building [VDA5050](https://www.vda.de/) systems —
both sides of the protocol:

- **AGV/AMR side** — make a robot VDA5050-compatible (receive orders, traverse
  nodes/edges, run actions, publish state).
- **Master side** — build a custom VDA5050 master to manage a fleet.

The core is transport- and robot-agnostic: it owns the protocol (MQTT, order
traversal, blocking-aware action scheduling, state reporting) and hands robot-
or application-specific behaviour to you through small callbacks.

## What's inside

| Package | Language | Description |
|---------|----------|-------------|
| [`vda5050_core`](vda5050_core/) | C++ | The VDA5050 library: client (AGV), master, adapter facade, types, MQTT transport. |
| [`vda5050_core_py`](vda5050_core_py/) | Python | pybind11 bindings over the AGV-side `RobotRuntime` facade, plus runnable examples. |

## Featured example: VDA5050 → TurtleBot3 coffee delivery

A full end-to-end demo: a master sends multi-node coffee orders, and a
simulated TurtleBot3 navigates with **Nav2**, picks up the coffee, delivers it,
and returns to base — one order at a time. It shows the intended split:
navigation and `pick`/`drop` actions live in the example, while order traversal
and action scheduling come from the core.

**Full guide (how it works, customizing, troubleshooting):**
[`vda5050_core_py/turtlebot3/ReadMe.md`](vda5050_core_py/turtlebot3/ReadMe.md)

### Quick start

**Prerequisites:** ROS 2 Jazzy + Gazebo (gz), `turtlebot3_gazebo`,
`turtlebot3_navigation2`, `nav2_simple_commander`, `mosquitto`, `paho-mqtt`. The
demo map of `turtlebot3_house` is **bundled** at
`vda5050_core_py/turtlebot3/maps/` — no need to create one.

**Build once:**

```bash
cd ~/vda5050_core
colcon build --symlink-install
source install/setup.bash
```

**Run (5 terminals)**

```bash
# 1. Gazebo simulation
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo turtlebot3_house.launch.py

# 2. Nav2 + AMCL with the saved map
#    Then in RViz click "2D Pose Estimate" at the robot's real location.
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
    use_sim_time:=True \
    map:=$HOME/vda5050_core/vda5050_core_py/turtlebot3/maps/house_office_map.yaml

# 3. MQTT broker
mosquitto -p 1883

# 4. AGV client (waits for Nav2, then for orders)
source ~/vda5050_core/install/setup.bash
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 example_turtlebot3_client.py

# 5. Master (publishes the coffee orders)
source ~/vda5050_core/install/setup.bash
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 publish_turtlebot3_route.py
```

> Nothing drives until you set the **2D Pose Estimate** in RViz so AMCL
> localizes. See the full guide for expected output and troubleshooting.

## Contributing & license

- Contribution guidelines: [CONTRIBUTING.md](CONTRIBUTING.md)
- Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).
