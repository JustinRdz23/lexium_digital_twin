#!/usr/bin/env python3
"""
Lexium Command Bridge
=====================
Subscribes to /lexium/joint_target (Float64MultiArray, radians)
and forwards each target to the real arm via JAKA JSON/TLS.

Data flow:
  MoveIt
    → C++ action server (/arm_controller/follow_joint_trajectory)
      → /lexium/joint_target  (this node subscribes here)
        → JAKA JSON/TLS → real arm
"""

import math
import ssl
import socket
import json
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray


# ── Connection config ──────────────────────────────────────────────
COBOT_HOST = '10.5.5.100'
COBOT_PORT = 10001

# Motion parameters — adjust to taste
MOVE_SPEED = 10.0   # % of max speed  (1-100)
MOVE_ACCEL = 10.0   # % of max accel  (1-100)


def _tls_context() -> ssl.SSLContext:
    """Accept the cobot's self-signed certificate."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class LexiumCommandBridge(Node):

    def __init__(self):
        super().__init__('lexium_command_bridge')

        self._lock = threading.Lock()

        # Subscribe to joint targets from the C++ action server
        self.sub_ = self.create_subscription(
            Float64MultiArray,
            '/lexium/joint_target',
            self.on_joint_target,
            10
        )

        self.get_logger().info(
            'Lexium command bridge ready — '
            f'listening on /lexium/joint_target, '
            f'forwarding to {COBOT_HOST}:{COBOT_PORT}'
        )

    # ── helpers ───────────────────────────────────────────────────

    def _send_command(self, cmd: dict) -> dict:
        """
        Open a fresh TLS connection, send one JSON command, return response.

        A new connection per command is intentional — the JAKA controller
        closes the socket after each response, so reusing a socket causes
        broken-pipe errors on the second call.
        """
        ctx = _tls_context()
        with socket.create_connection(
            (COBOT_HOST, COBOT_PORT), timeout=5.0
        ) as raw:
            with ctx.wrap_socket(raw) as tls:
                payload = json.dumps(cmd) + '\n'
                tls.send(payload.encode('utf-8'))
                response = tls.recv(4096).decode('utf-8').strip()
                return json.loads(response)

    # ── subscriber callback ───────────────────────────────────────

    def on_joint_target(self, msg: Float64MultiArray):
        """
        Called every time the C++ action server publishes a joint target.

        msg.data  — 6 floats, joint positions in RADIANS
                     [J1, J2, J3, J4, J5, J6]

        The JAKA API expects DEGREES, so we convert here.
        """
        if len(msg.data) != 6:
            self.get_logger().error(
                f'Expected 6 joint values, got {len(msg.data)}'
            )
            return

        # Convert radians → degrees
        joints_deg = [math.degrees(r) for r in msg.data]

        self.get_logger().info(
            'Received joint target (deg): '
            + '  '.join(f'{j:.2f}°' for j in joints_deg)
        )

        # Build JAKA joint_move command
        cmd = {
            'cmdName':       'joint_move',
            'relFlag':       0,          # 0 = absolute position
            'jointPosition': joints_deg,
            'speed':         MOVE_SPEED,
            'accel':         MOVE_ACCEL,
        }

        # Execute in a separate thread so we don't block the ROS executor
        with self._lock:
            threading.Thread(
                target=self._execute_move,
                args=(cmd, joints_deg),
                daemon=True
            ).start()

    def _execute_move(self, cmd: dict, joints_deg: list):
        """Send the move command and log the result."""
        try:
            response = self._send_command(cmd)
            error_code = response.get('errorCode', '-1')
            error_msg  = response.get('errorMsg', '')

            if error_code == '0':
                self.get_logger().info(
                    'Arm move accepted ✓  '
                    + '  '.join(f'{j:.2f}°' for j in joints_deg)
                )
            else:
                self.get_logger().error(
                    f'Arm move FAILED — code={error_code}  msg={error_msg}'
                )

        except Exception as exc:
            self.get_logger().error(
                f'TLS send failed: {exc}'
            )


def main(args=None):
    rclpy.init(args=args)
    node = LexiumCommandBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()