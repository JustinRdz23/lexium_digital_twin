from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os
import xacro


def generate_launch_description():

    pkg_share = get_package_share_directory('lexium_digital_twin')

    # Load the combined workcell xacro (workcell + arm)
    xacro_file = os.path.join(
        pkg_share,
        'urdf',
        'workcell.urdf.xacro'
    )

    # Process xacro → URDF string
    robot_description = xacro.process_file(xacro_file).toxml()

    rviz_config = os.path.join(
        pkg_share,
        'config',
        'display.rviz'
    )

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}]
        ),

        Node(
            package='rviz2',
            executable='rviz2',
            output='screen',
            arguments=['-d', rviz_config]
        ),
# Uncomment to test without hardware
        # Node(
        #     package='joint_state_publisher_gui',
        #     executable='joint_state_publisher_gui',
        #     output='screen',
        #     parameters=[{'robot_description': robot_description}]
        # )
    ])