# VDA5050 → TurtleBot3 (Nav2) coffee-delivery example

Drive a simulated TurtleBot3 from **VDA5050 orders**. A master sends coffee
orders over MQTT; the robot navigates with **Nav2**, picks up the coffee, and
delivers it.

`vda5050_core` owns the protocol (MQTT, order traversal, action scheduling,
state publishing). This example only supplies robot behaviour: turn each node
into a Nav2 goal, perform `pick`/`drop` actions, and mirror the live pose back
into the published State.

```
                  ┌──────────────────── vda5050_core ────────────────────┐
 order ──MQTT────▶│  order traversal + action scheduling (blockingType)   │
                  └───┬───────────────────────┬───────────────────────┬───┘
                      │ on_navigate(node)      │ on_action(pick/drop)  │ State
                      ▼                        ▼                       ▲
                 Nav2 goToPose            do the action           node_reached
                      │                        │                       │
                      ▼                        ▼                       │
              TurtleBot3 in Gazebo ───── /amcl_pose ──▶ PoseMirror ────┘
                                          (live agvPosition)
```

## What's included

- **Navigation + arrival** — each node becomes a Nav2 goal; on `SUCCEEDED` the
  client calls `node_reached`, so the order advances to the next node.
- **Node actions (pick / drop)** — the order carries a `pick` action at the
  coffee station and a `drop` action at the delivery node. The client's
  `on_action` executor performs them. The scheduling (blocking-aware) lives in
  `vda5050_core`; the meaning of `pick`/`drop` lives only in this example.
- **Multi-customer queue** — each customer is **one multi-node order**
  (`current pos → coffee_station → delivery`). The master sends one at a time
  and only dispatches the next after the current order is *fully* done
  (navigation **and** actions). When the queue empties it returns to base.
- **Live position** — `/amcl_pose` is mirrored into `State.agvPosition`, so the
  master sees the robot move, not just arrive.

## Files

| File | Side | Role |
|------|------|------|
| `example_turtlebot3_client.py` | AGV  | Nav2 driving, `pick`/`drop` execution, pose mirroring |
| `publish_turtlebot3_route.py`  | Master | Queues customer coffee orders, one at a time |

## Prerequisites

- **ROS 2 Jazzy** + **Gazebo (gz)**, with `turtlebot3_gazebo`,
  `turtlebot3_navigation2`, `nav2_simple_commander`
- **mosquitto** broker and **paho-mqtt** (`pip install paho-mqtt`)
- The demo map of `turtlebot3_house` is bundled at `maps/house_office_map.yaml`
  (next to these scripts) — no need to create one!
- This workspace built and sourced (see below)

Quick check that the tooling is present:

```bash
ros2 pkg prefix turtlebot3_gazebo turtlebot3_navigation2 nav2_simple_commander
which mosquitto
```

## Build once

```bash
cd ~/vda5050_core
colcon build --symlink-install
source install/setup.bash
```

<details>
<summary>If the build fails on <code>vda5050_core_py</code></summary>

```bash
cd ~/vda5050_core
rm -rf build/vda5050_core_py install/vda5050_core_py log
colcon build --packages-select vda5050_core_py --symlink-install
source install/setup.bash
```
</details>

## Run (5 terminals)

Open five terminals.

```bash
export TURTLEBOT3_MODEL=burger
```

**Terminal 1 - Gazebo simulation**
```bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo turtlebot3_house.launch.py
```

**Terminal 2 - Nav2 + AMCL with the saved map**
```bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
    use_sim_time:=True \
    map:=$HOME/vda5050_core/vda5050_core_py/turtlebot3/maps/house_office_map.yaml
```
> **In RViz, click "2D Pose Estimate"** and place it at the robot's real
> location so AMCL localizes. Nothing drives until this is done.

**Terminal 3 - MQTT broker**
```bash
mosquitto -p 1883
```

**Terminal 4 - AGV client** (waits for Nav2, then for orders)
```bash
source ~/vda5050_core/install/setup.bash
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 example_turtlebot3_client.py
```

**Terminal 5 - Master** (publishes the coffee orders)
```bash
source ~/vda5050_core/install/setup.bash
cd ~/vda5050_core/vda5050_core_py/turtlebot3
python3 publish_turtlebot3_route.py
```

## How it works

The master holds a list of customer requests:

```python
CUSTOMER_ORDERS = [
    {"customer_id": "customer_A", "delivery": "delivery_point"},
    {"customer_id": "customer_B", "delivery": "office_desk"},
]
```

For each customer it builds **one multi-node order** and walks it in sequence:

```
current position  ──▶  coffee_station  ──▶  delivery node
   (node seq 0)         (node seq 2)         (node seq 4)
                        action: pick         action: drop
                        (HARD)               (HARD)
```

The start node is the robot's live pose from `State.agvPosition` (falling back
to a fixed pose before the first State arrives). After all customers are served,
the master sends a final **return-to-base** order to `return_point` (toggle with
`RETURN_TO_BASE`).

**One order at a time.** Before dispatching, and before declaring a job done,
the master waits until the State reports the robot fully idle:

- `nodesLeft == 0`, `driving == False`, `lastNodeId == delivery node`, **and**
- no `actionStates` still `WAITING / INITIALIZING / RUNNING / PAUSED`.

That last condition is what makes the next order wait for the HARD `drop` to
finish, not just for navigation. A 180 s per-job timeout is the safety net.

### Customize

- **Destinations / customers** — edit `DESTINATIONS` and `CUSTOMER_ORDERS` in
  `publish_turtlebot3_route.py`. Keep `mapId == "map"` and use free-space
  coordinates from your map.
- **Action behaviour** — edit the `on_action` executor in
  `example_turtlebot3_client.py` (e.g. drive a gripper instead of sleeping).
- **Your own map** — the bundled map fits `turtlebot3_house`. To use a different
  world, generate a map (e.g. `turtlebot3_cartographer` SLAM, then
  `ros2 run nav2_map_server map_saver_cli -f maps/<name>`), point the `map:=`
  arg at it, and update the `DESTINATIONS` coordinates to free space on it.

## Expected output

Master, per customer (abridged):

```
[master] queueing customer orders: customer_A, customer_B
[master] queued customer_A -> delivery_point (depth 1)
[master] dispatch coffee_job_1_customer_A: current_start_1 -> coffee_station -> delivery_point
[state ] lastNode=coffee_station nodesLeft=1 driving=False activeActions=1 pos=(8.61, 3.05, 0.00)
[master] robot busy, waiting to dispatch (nodesLeft=1 driving=False activeActions=1)
[master] done: customer_A served at delivery_point
```

Client:

```
[tb3] on_navigate called for coffee_station
[tb3] reached coffee_station -> node_reached
[tb3] action 'pick' (pick_coffee_job_1_customer_A): picking up coffee...
[tb3] action 'pick' done
[tb3] on_navigate called for delivery_point
[tb3] reached delivery_point -> node_reached
[tb3] action 'drop' (drop_coffee_job_1_customer_A): dropping off coffee...
[tb3] action 'drop' done
```

## Troubleshooting

- **Client hangs at "waiting for Nav2 to become active", or `pos` stays `-`** —
  set the **2D Pose Estimate** in RViz so AMCL localizes.
- **Robot doesn't move / goal rejected** — order coordinates must be in the
  `map` frame (`nodePosition.mapId == "map"`) and in free space on your map.
- **Next order fires too early** — make sure the client is the current version:
  it must register `on_action` so `pick`/`drop` report `FINISHED`; otherwise the
  actions stay `RUNNING` and the master waits (correctly) forever.
- **First node**: the client acks the first node after boot without driving (it
  assumes the robot is already localized there), so each order's start node is
  free.
