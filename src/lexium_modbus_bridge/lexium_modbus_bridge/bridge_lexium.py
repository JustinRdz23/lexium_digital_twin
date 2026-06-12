import math
import struct

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState

from pymodbus.client import ModbusTcpClient


class LexiumBridge(Node):

    def __init__(self):
        super().__init__('lexium_bridge')

        self.publisher_ = self.create_publisher(
            JointState,
            '/joint_states',
            10
        )

        self.client = ModbusTcpClient(
            host='192.168.1.252',
            port=6502
        )

        if not self.client.connect():
            self.get_logger().error("Failed to connect to Lexium")
            raise RuntimeError("Modbus connection failed")

        self.joint_names = [
            "Joint_1",
            "Joint_2",
            "Joint_3",
            "Joint_4",
            "Joint_5",
            "Joint_6",
        ]

        self.timer = self.create_timer(
            0.05,  # 20 Hz
            self.timer_callback
        )

        self.get_logger().info("Lexium bridge started")

    def regs_to_float(self, reg1, reg2):
        raw = struct.pack(">HH", reg1, reg2)
        return struct.unpack(">f", raw)[0]

    def timer_callback(self):

        try:

            result = self.client.read_input_registers(
                address=382,
                count=12,
                device_id=0
            )

            if result.isError():
                self.get_logger().warn("Modbus read failed")
                return

            regs = result.registers

            positions_deg = []

            for i in range(0, 12, 2):

                value = self.regs_to_float(
                    regs[i],
                    regs[i + 1]
                )

                positions_deg.append(value)

            positions_rad = [
                math.radians(x)
                for x in positions_deg
            ]

            msg = JointState()

            msg.header.stamp = (
                self.get_clock()
                .now()
                .to_msg()
            )

            msg.name = self.joint_names
            msg.position = positions_rad

            self.publisher_.publish(msg)

        except Exception as e:
            self.get_logger().error(
                f"Exception: {str(e)}"
            )

    def destroy_node(self):

        self.client.close()

        super().destroy_node()


def main(args=None):

    rclpy.init(args=args)

    node = LexiumBridge()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':
    main()