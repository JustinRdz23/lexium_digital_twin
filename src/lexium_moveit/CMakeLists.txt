set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
cmake_minimum_required(VERSION 3.8)
project(lexium_moveit)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# --------------------------------------------------
# Dependencies
# --------------------------------------------------

find_package(ament_cmake REQUIRED)

find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)

find_package(std_msgs REQUIRED)

find_package(control_msgs REQUIRED)
find_package(trajectory_msgs REQUIRED)

# --------------------------------------------------
# Executable
# --------------------------------------------------

add_executable(
  lexium_trajectory_server
  src/lexium_trajectory_server.cpp
)

ament_target_dependencies(
  lexium_trajectory_server
  rclcpp
  rclcpp_action
  std_msgs
  control_msgs
  trajectory_msgs
)
# --------------------------------------------------
# Install
# --------------------------------------------------

install(
  TARGETS lexium_trajectory_server
  DESTINATION lib/${PROJECT_NAME}
)

# --------------------------------------------------
# Testing
# --------------------------------------------------

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)

  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)

  ament_lint_auto_find_test_dependencies()
endif()

ament_package()