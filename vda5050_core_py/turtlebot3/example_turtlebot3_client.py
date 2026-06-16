"""TurtleBot3 (Nav2) client.

The smallest end-to-end loop:
    on_navigate(node)  ->  Nav2 navigate_to_pose goal  ->  TB3 drives in Gazebo
      ->  Nav2 result SUCCEEDED  ->  node_reached  ->  strategy dispatches next node
"""

from __future__ import annotations

import math
import threading
import time

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node as RosNode
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)

import vda5050_core_py as vda


# Stores settings for MQTT, VDA5050 identity and Nav2
CONFIG = {
    "broker": "tcp://localhost:1883",
    "client_id": "turtlebot3_agv",
    "manufacturer": "Manufacturer",
    "serial_number": "S001",
    "map_frame": "map",
    "nav_timeout": 120.0,
    "poll_interval": 0.5,
}


def _yaw_to_quat_z_w(theta: float) -> tuple[float, float]:
    """Yaw (rad) -> (z, w) of a +Z-only rotation quaternion."""
    half = theta * 0.5
    return math.sin(half), math.cos(half)


def _quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """(x, y, z, w) quaternion -> yaw (rad) about +Z."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class PoseMirror(RosNode):
    """Subscribes to /amcl_pose and pushes each pose to rep.set_agv_position()."""

    def __init__(self, rep: vda.Reporter) -> None:
        super().__init__("vda5050_pose_mirror")
        self._rep = rep

        # AMCL publishes /amcl_pose as RELIABLE + TRANSIENT_LOCAL.
        # Matching this lets us receive the latest latched pose even if the
        # robot is stationary.
        amcl_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_pose,
            amcl_qos,
        )

    def _on_pose(self, msg: PoseWithCovarianceStamped) -> None:
        p = msg.pose.pose

        agv = vda.AGVPosition()
        agv.position_initialized = True
        agv.x = p.position.x
        agv.y = p.position.y
        agv.theta = _quat_to_yaw(
            p.orientation.x,
            p.orientation.y,
            p.orientation.z,
            p.orientation.w,
        )
        agv.map_id = CONFIG["map_frame"]

        self._rep.set_agv_position(agv)


def _goal_for(node: vda.Node, navigator: BasicNavigator) -> PoseStamped:
    """Build Nav2 goal from VDA5050 node."""

    pos = node.node_position

    if pos is None:
        raise ValueError(f"Node {node.node_id} has no nodePosition")

    goal = PoseStamped()
    goal.header.frame_id = CONFIG["map_frame"]
    goal.header.stamp = navigator.get_clock().now().to_msg()

    goal.pose.position.x = float(pos.x)
    goal.pose.position.y = float(pos.y)

    qz, qw = _yaw_to_quat_z_w(float(pos.theta))
    goal.pose.orientation.z = qz
    goal.pose.orientation.w = qw

    return goal


def _drive_to_node(
    node: vda.Node,
    rep: vda.Reporter,
    navigator: BasicNavigator,
) -> None:
    """Blocking Nav2 navigate; calls node_reached on success. Runs in worker thread."""

    try:
        pos = node.node_position

        if pos is None:
            print(f"[tb3] ERROR: node {node.node_id} has no nodePosition", flush=True)
            return

        print(
            f"[tb3] navigate to {node.node_id} "
            f"({pos.x}, {pos.y}, theta={pos.theta})",
            flush=True,
        )

        # Tell VDA5050 State that robot is driving
        rep.set_driving(True)

        # Send Nav2 goal
        goal = _goal_for(node, navigator)
        navigator.goToPose(goal)

        deadline = time.monotonic() + CONFIG["nav_timeout"]

        while not navigator.isTaskComplete():
            feedback = navigator.getFeedback()

            if feedback:
                print(
                    f"[tb3] feedback: distance_remaining="
                    f"{feedback.distance_remaining:.2f}",
                    flush=True,
                )

            if time.monotonic() > deadline:
                navigator.cancelTask()
                print(f"[tb3] timeout driving to {node.node_id}", flush=True)
                break

            time.sleep(CONFIG["poll_interval"])

        rep.set_driving(False)

        result = navigator.getResult()

        if result == TaskResult.SUCCEEDED:
            print(f"[tb3] reached {node.node_id} -> node_reached", flush=True)
            rep.node_reached(node.node_id, node.sequence_id)
        else:
            print(
                f"[tb3] move to {node.node_id} ended {result!r}; not advancing",
                flush=True,
            )

    except Exception as e:
        rep.set_driving(False)
        print(f"[tb3] ERROR while driving to {node.node_id}: {e}", flush=True)


def main() -> int:
    rclpy.init()

    navigator = BasicNavigator()

    print(
        "[tb3] waiting for Nav2 to become active "
        "(set the initial pose in RViz if it hangs)...",
        flush=True,
    )

    navigator.waitUntilNav2Active(localizer="amcl")

    print("[tb3] Nav2 active", flush=True)

    runtime = vda.RobotRuntime(
        broker=CONFIG["broker"],
        client_id=CONFIG["client_id"],
        manufacturer=CONFIG["manufacturer"],
        serial_number=CONFIG["serial_number"],
    )

    rep = runtime.reporter()

    # Mirror /amcl_pose -> State.agvPosition on its own executor/thread
    pose_mirror = PoseMirror(rep)
    pose_executor = SingleThreadedExecutor()
    pose_executor.add_node(pose_mirror)

    threading.Thread(
        target=pose_executor.spin,
        daemon=True,
    ).start()

    def on_navigate(node: vda.Node, edge) -> None:
        print(f"[tb3] on_navigate called for {node.node_id}", flush=True)

        threading.Thread(
            target=_drive_to_node,
            args=(node, rep, navigator),
            daemon=True,
        ).start()

    ACTION_DWELL_S = 5.0

    def on_action(action: vda.Action) -> vda.ActionExecution:
        kind = action.action_type
        if kind in ("pick", "drop"):
            verb = "picking up coffee" if kind == "pick" else "dropping off coffee"
            print(f"[tb3] action {kind!r} ({action.action_id}): {verb}...", flush=True)
            time.sleep(ACTION_DWELL_S)
            print(f"[tb3] action {kind!r} done", flush=True)
            return vda.ActionExecution(vda.ActionStatus.FINISHED)

        print(f"[tb3] unsupported action type {kind!r}; failing", flush=True)
        return vda.ActionExecution(
            vda.ActionStatus.FAILED, f"unsupported action: {kind}"
        )

    runtime.on_navigate(on_navigate)
    runtime.on_action(on_action)
    runtime.start()

    print("[tb3] runtime started; waiting for orders. Ctrl+C to exit.", flush=True)

    try:
        vda.run_until_signal(runtime)

    finally:
        pose_executor.shutdown()
        pose_mirror.destroy_node()
        navigator.destroy_node()
        rclpy.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())