# VDA5050 → TurtleBot3 (Nav2) example

Drives a simulated TurtleBot3 from VDA5050 orders. The C++ core
(`vda5050_core_py`) owns MQTT + order traversal; this example turns each
`nodePosition` into a Nav2 goal, reports arrival, and mirrors the robot's live
pose back into the published State.

```
order ──MQTT──▶ vda5050_core ──on_navigate(node)──▶ Nav2 goToPose ──▶ TurtleBot3 in Gazebo
                     ▲                                                      │
                     ├──── node_reached ◀── Nav2 result SUCCEEDED ◀─────────┘
                     │
   /amcl_pose ──▶ PoseMirror ──▶ rep.set_agv_position() ──▶ State.agvPosition (live)
```

What's included:
- **Navigation + arrival** — each node becomes a Nav2 goal; on SUCCEEDED the
  client calls `node_reached` so the order advances.
- **Live position** — `/amcl_pose` is mirrored into `State.agvPosition`, so the
  master sees the robot move, not just arrive.
- **Multi-customer coffee queue** — each customer is ONE multi-node order
  (current pos → coffee_station → delivery); the master sends one at a time and
  returns to base when the queue is empty (see below).
- **Node actions (pickup/dropoff)** — the order carries a `pick` action on
  `coffee_station` and a `drop` action on the delivery node. The client
  registers an `on_action` executor that dispatches on `action.action_type`.
  The action mechanism (blocking-aware scheduling) lives in vda5050_core; the
  `pick`/`drop` meaning lives only in this example.

Not done yet: battery state.

## Files

| File | Role |
|------|------|
| `example_turtlebot3_client.py` | AGV side: Nav2 driving + pose mirroring |
| `publish_turtlebot3_route.py`  | Master side: coffee-delivery queue |

## How the queue works

`publish_turtlebot3_route.py` holds a `DEMO_ROUTE` of destinations
(`coffee_station → delivery_point → return_point (charging station)`, house-map coords). For each
job it:

1. builds a 2-node order (robot's **current position → destination**), the start
   node read from the live `State.agvPosition`,
2. publishes it and waits until the State reports the order complete
   (`nodesLeft == 0`, `driving == False`, `lastNodeId == destination`), with a
   180 s per-job safety timeout,
3. moves to the next job — chaining so each order starts where the last ended.

## Prerequisites

- ROS2 Jazzy, Gazebo (gz), `turtlebot3_gazebo`, `turtlebot3_navigation2`,
  `nav2_simple_commander`
- `mosquitto` broker, `paho-mqtt` (publisher)
- `vda5050_core_py` built and importable (`source install/setup.bash`)
- A saved map (`house_office_map.yaml`) for `turtlebot3_house`

## Run (each in its own shell)

```bash
source ~/.bashrc
export TURTLEBOT3_MODEL=burger  # Set in every shell

# 1. Sim
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo turtlebot3_house.launch.py

# 2. Nav2 + AMCL with saved map, then set the initial pose in RViz
#    (Need to set "2D Pose Estimate" manually like exact location of the turtlebot3) so AMCL localizes before driving.
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
    use_sim_time:=True map:=$HOME/house_office_map.yaml

# 3. Broker
mosquitto -p 1883

# 4. Need to build and source the workspace
cd ~/vda5050_core
colcon build --symlink-install
source install/setup.bash

# If build fails!! then try this!
cd ~/vda5050_core
rm -rf build/vda5050_core_py install/vda5050_core_py log
colcon build --packages-select vda5050_core_py --symlink-install
source install/setup.bash

# 5. AGV client (waits for Nav2 active, then for orders)
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 example_turtlebot3_client.py

# 6. Master: drain the coffee-delivery queue, watch State stream back
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 publish_turtlebot3_route.py
```

Expected master output: a `[state ]` line per update with a changing
`pos=(x, y, theta)`, a `[master] dispatch: ...` line per order, and a
`[master] done: reached <dest>` line as each destination is reached.

## Notes

- **Frame**: Nav2 plans in `map`, so order `nodePosition.mapId` must be `"map"`
  and x/y must be map-frame coordinates (where AMCL is localized).
- **Localization first**: if the client hangs at "waiting for Nav2 to become
  active", or `pos` stays `-`, set the "2D Pose Estimate" in RViz.
- **First node**: the client acks the first node after boot without driving
  (it assumes the robot is localized there), so each order's start node is free.
