import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder




def generate_launch_description():
    # Force OMPL as the default planning pipeline
    planning_pipeline_config = {
        "planning_pipelines": ["ompl"],
        "default_planning_pipeline": "ompl",
    }
    # 1. Paths to your digital twin package where your actual URDF lives
    twin_package_share = get_package_share_directory("lexium_digital_twin")
    original_urdf_path = os.path.join(
        twin_package_share, 
        "urdf", 
        "Lexium_Cobot_L03S_3D-simpl.SLDASM.urdf"
    )

    # 2. Tell MoveIt where your real URDF sits AND attach the joint limits configuration
    moveit_config = (
        MoveItConfigsBuilder("lexium_digital_twin", package_name="lexium_moveit_config")
        .robot_description(file_path=original_urdf_path)
        .joint_limits(file_path=os.path.join(
            get_package_share_directory("lexium_moveit_config"), "config", "joint_limits.yaml"
        ))
        .planning_pipelines(pipelines=["ompl"]) # Ensure OMPL is loaded explicitly
        .to_moveit_configs()
    )

    # 3. Start Robot State Publisher (Streams the current joint configuration states)
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[moveit_config.robot_description],
    )

    # 4. Start MoveGroup node (The brains of MoveIt planning)
    run_move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[
            moveit_config.to_dict(),
            {"default_planning_pipeline": "ompl"}  # <--- ADD THIS LINE
        ],
    )

    # 5. Start RViz configured specifically for your MoveIt profile
    rviz_base = os.path.join(get_package_share_directory("lexium_moveit_config"), "config")
    rviz_config = os.path.join(rviz_base, "moveit.rviz")
    
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="log",
        arguments=["-d", rviz_config],
        parameters=[
            moveit_config.robot_description,
            moveit_config.robot_description_semantic,
            moveit_config.robot_description_kinematics,
        ],
    )

    # 6. Static TF Link between MoveIt's virtual frame and your real robot's physical base link
    static_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_transform_publisher",
        output="screen",
        arguments=["0", "0", "0", "0", "0", "0", "lexium_world", "base_link"]
    )

    return LaunchDescription([
        static_tf_node,
        robot_state_publisher,
        run_move_group_node,
        rviz_node,
    ])