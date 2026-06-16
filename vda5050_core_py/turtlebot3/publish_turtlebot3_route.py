"""Master-side coffee-delivery demo for the TurtleBot3 Nav2 VDA5050 example.

Represents multiple customer coffee requests. Each customer becomes ONE
multi-node VDA5050 order:
    current position -> coffee_station -> customer delivery location

The master sends only one order at a time and waits until the robot reaches
the final delivery node before dispatching the next customer. Each order's
first node is the robot's current position from live State.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


INTERFACE, VERSION, MANUF, SERIAL = "uagv", "2.0.0", "Manufacturer", "S001"
PREFIX = f"{INTERFACE}/{VERSION}/{MANUF}/{SERIAL}"
ORDER_TOPIC = f"{PREFIX}/order"
STATE_TOPIC = f"{PREFIX}/state"
MAP_ID = "map"

# Customer coffee-delivery requests. Each becomes ONE multi-node order:
#   current position -> coffee_station -> delivery location
CUSTOMER_ORDERS = [
    {"customer_id": "customer_A", "delivery": "delivery_point"},
    {"customer_id": "customer_B", "delivery": "office_desk"},
]

# Where the robot picks up every coffee before delivering it.
PICKUP = "coffee_station"

# After all customers are served, send the robot back to base (charging
# station). Set False to leave it parked at the last delivery instead.
RETURN_TO_BASE = True
HOME = "return_point"

# Named destinations in map-frame coordinates. The "delivery" values in
# CUSTOMER_ORDERS (plus PICKUP and HOME) must be keys here.
DESTINATIONS = {
    "coffee_station": {
        "x": 8.611273765563965,
        "y": 3.054003953933716,
        "theta": 0.0,
    },
    "delivery_point": {
        "x": -2.029632806777954,
        "y": 2.441532850265503,
        "theta": 0.0,
    },
    "office_desk": {
        "x": 7.022,
        "y": 4.669,
        "theta": 0.0,
    },
    "meeting_room": {
        "x": -1.678,
        "y": 4.969,
        "theta": 0.0,
    },
    # Charging / home base the robot returns to when the queue is empty.
    "return_point": {
        "x": 8.405553817749023,
        "y": -3.751394748687744,
        "theta": 0.0,
    },
}

# Fallback start pose, used only before the first State with agvPosition arrives
START = {
    "id": "start_point",
    "x": 8.405553817749023,
    "y": -3.751394748687744,
    "theta": 0.0,
}

ARRIVE_TIMEOUT = 180.0
POLL = 0.5
BUSY_LOG_INTERVAL = 5.0  # seconds between "still busy" logs while waiting to dispatch

_lock = threading.Lock()

_latest = {
    "lastNodeId": None,
    "nodesLeft": None,
    "driving": None,
    "pos": None,
    "actionsActive": 0,
}

# VDA5050 actionStatus values that mean the action is NOT yet done. Anything
# else (FINISHED / FAILED, or an unknown status) is treated as settled. These
# strings already arrive in every State message's actionStates; the master just
# needs to read them.
ACTIVE_ACTION_STATUSES = {"WAITING", "INITIALIZING", "RUNNING", "PAUSED"}


def count_active_actions(action_states) -> int:
    """Number of actionStates still WAITING / INITIALIZING / RUNNING / PAUSED.

    Casing is normalised, and a missing/empty actionStates list (older State
    messages) counts as zero so the demo still works without action support.
    """
    count = 0
    for a in action_states or []:
        status = str(a.get("actionStatus", "")).upper()
        if status in ACTIVE_ACTION_STATUSES:
            count += 1
    return count


def make_mqtt(client_id: str):
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
    except (AttributeError, TypeError):
        return mqtt.Client(client_id)


def on_state(client, userdata, msg):
    """Update latest AGV state from MQTT state topic."""
    s = json.loads(msg.payload)

    pos = s.get("agvPosition") or {}
    have_pos = bool(pos.get("positionInitialized"))

    active_actions = count_active_actions(s.get("actionStates"))

    with _lock:
        _latest["lastNodeId"] = s.get("lastNodeId")
        _latest["nodesLeft"] = len(s.get("nodeStates") or [])
        _latest["driving"] = s.get("driving")
        _latest["actionsActive"] = active_actions

        if have_pos:
            _latest["pos"] = {
                "x": pos["x"],
                "y": pos["y"],
                "theta": pos.get("theta", 0.0),
            }

    pos_str = (
        f"({pos['x']:.2f}, {pos['y']:.2f}, {pos.get('theta', 0.0):.2f})"
        if have_pos
        else "-"
    )

    print(
        f"[state ] lastNode={s.get('lastNodeId') or '-':<14} "
        f"nodesLeft={len(s.get('nodeStates') or [])} "
        f"driving={s.get('driving')} activeActions={active_actions} "
        f"pos={pos_str}",
        flush=True,
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def current_start() -> dict:
    """Use robot's current live pose as the start node."""
    with _lock:
        node_id = _latest["lastNodeId"] or START["id"]
        pos = _latest["pos"]

    if pos:
        return {
            "id": node_id,
            "x": pos["x"],
            "y": pos["y"],
            "theta": pos["theta"],
        }

    return dict(START, id=node_id)


def make_action(action_type: str, action_id: str, blocking: str = "HARD") -> dict:
    """Build a VDA5050 node action (e.g. coffee pick/drop).

    blocking HARD means the robot runs it standing still, with no other action
    active — the right default for a physical pick/drop. The AGV client decides
    what each action_type actually does via its on_action executor.
    """
    return {
        "actionId": action_id,
        "actionType": action_type,
        "blockingType": blocking,
        "actionParameters": [],
    }


def build_order(
    header_id: int,
    order_id: str,
    waypoints: "list[tuple[str, dict, list]]",
) -> dict:
    """Build a multi-node VDA5050 order from an ordered list of waypoints.

    `waypoints` is a list of (node_id, pose, actions) tuples walked in order,
    where actions is a (possibly empty) list of action dicts from make_action,
    e.g.
        [(start_id, start_pose, []),
         ("coffee_station", coffee_pose, [pick_action]),
         (delivery_id, delivery_pose, [drop_action])]
    Nodes get even sequenceIds (0, 2, 4, ...); edges connect consecutive
    nodes with odd sequenceIds (1, 3, ...). So a 3-waypoint coffee job yields
    nodes 0/2/4 and edges 1/3 — exactly the VDA5050 traversal the AGV client
    walks via on_navigate / node_reached, running each node's actions on arrival.
    """
    nodes = []
    edges = []

    for i, (node_id, p, actions) in enumerate(waypoints):
        nodes.append(
            {
                "nodeId": node_id,
                "sequenceId": 2 * i,
                "released": True,
                "actions": actions,
                "nodePosition": {
                    "x": p["x"],
                    "y": p["y"],
                    "theta": p["theta"],
                    "mapId": MAP_ID,
                },
            }
        )

        if i > 0:
            prev_id = waypoints[i - 1][0]
            edges.append(
                {
                    "edgeId": f"edge_{prev_id}_to_{node_id}",
                    "sequenceId": 2 * i - 1,
                    "released": True,
                    "startNodeId": prev_id,
                    "endNodeId": node_id,
                    "actions": [],
                }
            )

    return {
        "headerId": header_id,
        "timestamp": now_iso(),
        "version": VERSION,
        "manufacturer": MANUF,
        "serialNumber": SERIAL,
        "orderId": order_id,
        "orderUpdateId": 0,
        "nodes": nodes,
        "edges": edges,
    }


def wait_until_idle(stop: threading.Event) -> bool:
    """Block until the robot is fully idle: not navigating AND no active actions.

    Idle means nodesLeft is 0/None, driving is false, and no actionState is
    still WAITING / INITIALIZING / RUNNING / PAUSED — so a HARD pick/drop must
    finish before the next order is dispatched. Waits indefinitely so a queued
    order is never dropped; logs why it is still waiting every
    BUSY_LOG_INTERVAL seconds. Returns False if `stop` is set while waiting
    (shutdown), True once the robot is idle.
    """
    next_log = 0.0

    while not stop.is_set():
        with _lock:
            nodes_left = _latest["nodesLeft"]
            driving = _latest["driving"]
            active_actions = _latest["actionsActive"]

        if nodes_left in (0, None) and not driving and active_actions == 0:
            return True

        now = time.monotonic()
        if now >= next_log:
            print(
                f"[master] robot busy, waiting to dispatch "
                f"(nodesLeft={nodes_left} driving={driving} "
                f"activeActions={active_actions})",
                flush=True,
            )
            next_log = now + BUSY_LOG_INTERVAL

        time.sleep(POLL)

    return False


def wait_for_arrival(dest_id: str, timeout_s: float) -> bool:
    """Wait until the robot reaches dest_id AND its node actions are done.

    The job is complete only when navigation has finished (nodesLeft == 0,
    driving False, lastNodeId == dest_id) and no actionState is still active —
    so the HARD drop at the delivery node must report FINISHED/FAILED before
    this returns.
    """
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        with _lock:
            done = (
                _latest["nodesLeft"] == 0
                and _latest["driving"] is False
                and _latest["lastNodeId"] == dest_id
                and _latest["actionsActive"] == 0
            )

        if done:
            return True

        time.sleep(POLL)

    return False


def dispatcher(client, jobs: "queue.Queue[dict | None]", stop: threading.Event):
    """Send one customer order at a time.

    Each job is a dict: {"customer_id", "delivery", optional "pickup"}. With
    pickup (the default) the order is current -> coffee_station -> delivery;
    without it (the return-home leg) it is current -> delivery. The next job is
    only dispatched after the robot reaches the final delivery node.
    """
    header_id = 1

    while not stop.is_set():
        job = jobs.get()

        if job is None:
            jobs.task_done()
            break

        customer_id = job["customer_id"]
        delivery_id = job["delivery"]
        pickup = job.get("pickup", True)

        if delivery_id not in DESTINATIONS:
            print(f"[master] unknown delivery location: {delivery_id}", flush=True)
            jobs.task_done()
            continue

        # Wait (indefinitely) for the robot to be free, then dispatch. The job
        # stays queued rather than being dropped. Only bails out on shutdown.
        if not wait_until_idle(stop):
            jobs.task_done()
            break

        start = current_start()
        start["id"] = f"current_start_{header_id}"

        order_id = f"coffee_job_{header_id}_{customer_id}"

        # current position -> [coffee_station: pick] -> delivery node: drop.
        # The return-home leg (pickup=False) carries no coffee actions.
        waypoints = [(start["id"], start, [])]
        if pickup:
            waypoints.append(
                (PICKUP, DESTINATIONS[PICKUP], [make_action("pick", f"pick_{order_id}")])
            )
            delivery_actions = [make_action("drop", f"drop_{order_id}")]
        else:
            delivery_actions = []
        waypoints.append((delivery_id, DESTINATIONS[delivery_id], delivery_actions))

        route = " -> ".join(node_id for node_id, *_ in waypoints)
        print(f"\n[master] dispatch {order_id}: {route}", flush=True)

        order = build_order(header_id, order_id, waypoints)

        client.publish(ORDER_TOPIC, json.dumps(order))
        print(f"[master] published order to {ORDER_TOPIC}", flush=True)

        header_id += 1

        # Wait for the FINAL node (customer delivery), not the coffee pickup.
        if wait_for_arrival(delivery_id, ARRIVE_TIMEOUT):
            print(f"[master] done: {customer_id} served at {delivery_id}", flush=True)
        else:
            print(
                f"[master] TIMEOUT waiting for {delivery_id} ({customer_id})",
                flush=True,
            )

        jobs.task_done()


def main() -> int:
    client = make_mqtt("tb3_master_auto")
    client.on_message = on_state

    client.connect("localhost", 1883, 60)
    client.subscribe(STATE_TOPIC)
    client.loop_start()

    jobs: "queue.Queue[dict | None]" = queue.Queue()
    stop = threading.Event()

    disp = threading.Thread(
        target=dispatcher,
        args=(client, jobs, stop),
        daemon=True,
    )
    disp.start()

    try:
        print("[master] waiting a few seconds for initial state...", flush=True)
        time.sleep(3.0)

        print(
            "[master] queueing customer orders:",
            ", ".join(j["customer_id"] for j in CUSTOMER_ORDERS),
            flush=True,
        )

        for job in CUSTOMER_ORDERS:
            jobs.put(job)
            print(
                f"[master] queued {job['customer_id']} -> {job['delivery']} "
                f"(depth {jobs.qsize()})",
                flush=True,
            )

        # Final leg: drive back to base (charging station) once all customers
        # are served. No coffee pickup on the way home.
        if RETURN_TO_BASE:
            jobs.put({"customer_id": "base", "delivery": HOME, "pickup": False})
            print(f"[master] queued return to base -> {HOME}", flush=True)

        # Wait until all queued jobs are completed
        jobs.join()

    except KeyboardInterrupt:
        print("\n[master] interrupted.", flush=True)

    finally:
        stop.set()
        jobs.put(None)
        disp.join(timeout=2.0)
        client.loop_stop()
        client.disconnect()

    print("[master] stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())