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

        # ============================================================
        # MODBUS REGISTER MAP CONFIGURATION (Placeholders)
        # ============================================================
        # Arm config
        self.ARM_START_REG = 382
        self.ARM_REG_COUNT = 12  # 6 joints * 2 registers each

        # Workcell config (Update these once registers are known)
        self.RAIL_SIGNAL_REG = 400   # Register containing the rail target command
        self.PISTON_SIGNAL_REG = 401 # Register containing the piston target command

        # Physical limit ends (matching your Xacro limits)
        self.RAIL_LIMIT_LOWER = 0.0
        self.RAIL_LIMIT_UPPER = 0.5

        self.PISTON_LIMIT_LOWER = 0.0
        self.PISTON_LIMIT_UPPER = 0.5
        # ============================================================

        # Joint tracking list — now including the 2 linear components
        self.joint_names = [
            "Joint_1",
            "Joint_2",
            "Joint_3",
            "Joint_4",
            "Joint_5",
            "Joint_6",
            "rail_joint",
            "piston_joint"
        ]

        self.timer = self.create_timer(
            0.05,  # 20 Hz
            self.timer_callback
        )

        self.get_logger().info("Lexium bridge started with Workcell controls")

    def regs_to_float(self, reg1, reg2):
        raw = struct.pack(">HH", reg1, reg2)
        return struct.unpack(">f", raw)[0]

    def timer_callback(self):
        try:
            # 1. READ ARM ROBOT JOINTS
            arm_result = self.client.read_input_registers(
                address=self.ARM_START_REG,
                count=self.ARM_REG_COUNT,
                device_id=0
            )

            if arm_result.isError():
                self.get_logger().warn("Modbus read for Arm joints failed")
                return

            arm_regs = arm_result.registers
            positions_deg = []

            for i in range(0, self.ARM_REG_COUNT, 2):
                value = self.regs_to_float(
                    arm_regs[i],
                    arm_regs[i + 1]
                )
                positions_deg.append(value)

            positions_rad = [
                math.radians(x)
                for x in positions_deg
            ]

            # 2. READ WORKCELL TARGET COMMANDS
            # Reading the rail target signal state
            rail_result = self.client.read_input_registers(
                address=self.RAIL_SIGNAL_REG,
                count=1,
                device_id=0
            )
            
            # Reading the piston target signal state
            piston_result = self.client.read_input_registers(
                address=self.PISTON_SIGNAL_REG,
                count=1,
                device_id=0
            )

            # Determine Rail Position based on signal state
            if not rail_result.isError() and rail_result.registers[0] == 1:
                rail_pos = self.RAIL_LIMIT_UPPER
            else:
                rail_pos = self.RAIL_LIMIT_LOWER

            # Determine Piston Position based on signal state
            if not piston_result.isError() and piston_result.registers[0] == 1:
                piston_pos = self.PISTON_LIMIT_UPPER
            else:
                piston_pos = self.PISTON_LIMIT_LOWER

            # Append the workcell positions to our master layout array
            positions_rad.append(rail_pos)
            positions_rad.append(piston_pos)

            # 3. BUILD AND PUBLISH THE JOINT STATE MESSAGE
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
                f"Exception in bridge cycle: {str(e)}"
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