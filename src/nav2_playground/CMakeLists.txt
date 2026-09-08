cmake_minimum_required(VERSION 3.20)
project(nav2_playground)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(nav2_waypoint_follower REQUIRED)
find_package(nav2_core REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(nav2_common REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

nav2_package()

set(library_name ${PROJECT_NAME})

install(DIRECTORY launch config maps DESTINATION share/${PROJECT_NAME})

ament_export_include_directories(include)
ament_export_libraries(${library_name})
ament_export_dependencies(ament_cmake
  rclcpp
  rclcpp_action
  geometry_msgs
  nav2_msgs
  nav2_waypoint_follower
  nav2_core
  pluginlib
  rclcpp_lifecycle)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)

  ament_lint_auto_find_test_dependencies()

endif()

ament_package()
