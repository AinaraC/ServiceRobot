# Copyright 2025 Intelligent Robotics Lab

# This file is part of the project Easy Navigation (EasyNav in short)
# licensed under the GNU General Public License v3.0.
# See <http://www.gnu.org/licenses/> for details.

# Easy Navigation program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
from os.path import join

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    world_arg = DeclareLaunchArgument(
        'world', default_value=os.path.join(
            get_package_share_directory('aws_robomaker_small_house_world'),
            'worlds',
            'small_house.world'))

    gui_arg = DeclareLaunchArgument(
        'gui',
        default_value='true',
        description='Set to false to run gazebo headless',
    )

    lidar_range_arg = DeclareLaunchArgument(
        'lidar_range',
        default_value='3.0',
        description='Maximum range of the lidar sensor in meters'
    )

    gazebo_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch',
                         'gz_sim.launch.py')),
        launch_arguments={'gz_args': ['-r -s ', LaunchConfiguration('world')]}.items()
    )

    gazebo_client = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'),
                         'launch',
                         'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': [' -g ']}.items(),
        condition=IfCondition(LaunchConfiguration('gui')),
    )

    spawn_robot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('kobuki_description'),
            'launch/'), 'spawn.launch.py']),
        launch_arguments={
            'lidar_range': LaunchConfiguration('lidar_range'),
        }.items()
    )

    # Bridge
    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='bridge_ros_gz',
        parameters=[
            {
                'config_file': join(
                     get_package_share_directory('nav2_playground'),
                     'config', 'bridge', 'clock_bridge.yaml'
                ),
                'use_sim_time': True,
            }
        ],
        output='screen',
    )

    ld = LaunchDescription()
    ld.add_action(world_arg)
    ld.add_action(gui_arg)
    ld.add_action(lidar_range_arg)
    ld.add_action(gazebo_server)
    ld.add_action(gazebo_client)
    ld.add_action(spawn_robot)
    ld.add_action(ros_gz_bridge)

    return ld
