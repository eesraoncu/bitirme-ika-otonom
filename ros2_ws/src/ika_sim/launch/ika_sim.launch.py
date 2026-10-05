"""İKA deney sahasını TurtleBot 4 ile açar (Faz 3).

Kullanım (depo kökünden):
    ros2 launch ros2_ws/src/ika_sim/launch/ika_sim.launch.py

TurtleBot 4'ün turtlebot4_ignition.launch.py'si dünya arama yolunu
(IGN_GAZEBO_RESOURCE_PATH) baştan yazar; bizim worlds/ klasörümüz yolda kalmaz.
Bu dosya onun ignition.launch.py'sinin yaptığını tekrarlar ve yola worlds/'ü de
ekler. Robotu yine TurtleBot 4'ün turtlebot4_spawn.launch.py'si (0, 0)'a koyar.
"""
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node

WORLDS_DIR = Path(__file__).resolve().parent.parent / 'worlds'

ARGUMENTS = [
    DeclareLaunchArgument('world', default_value='ika_saha',
                          description='worlds/ altındaki dünya, uzantısız'),
    DeclareLaunchArgument('model', default_value='standard', choices=['standard', 'lite'],
                          description='TurtleBot 4 modeli'),
    DeclareLaunchArgument('rviz', default_value='false', choices=['true', 'false'],
                          description='RViz açılsın mı'),
]


def generate_launch_description():
    share = get_package_share_directory
    tb4_bringup = share('turtlebot4_ignition_bringup')

    # Dünyalar, robot modelleri ve TurtleBot 4'ün kendi dünyaları; ilk sırada bizimki
    resource_path = ':'.join([
        str(WORLDS_DIR),
        os.path.join(tb4_bringup, 'worlds'),
        os.path.join(share('irobot_create_ignition_bringup'), 'worlds'),
        str(Path(share('turtlebot4_description')).parent.resolve()),
        str(Path(share('irobot_create_description')).parent.resolve()),
    ])
    # TurtleBot 4'ün arayüz eklentileri (sağdaki HMI paneli)
    gui_plugin_path = ':'.join([
        os.path.join(share('turtlebot4_ignition_gui_plugins'), 'lib'),
        os.path.join(share('irobot_create_ignition_plugins'), 'lib'),
    ])

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(share('ros_ign_gazebo'), 'launch', 'ign_gazebo.launch.py')),
        launch_arguments=[('ign_args', [
            LaunchConfiguration('world'), '.sdf -r -v 4 --gui-config ',
            PathJoinSubstitution([tb4_bringup, 'gui', LaunchConfiguration('model'), 'gui.config']),
        ])])

    # Simülasyon saati ROS'a: use_sim_time ile çalışan her düğüm buna bakar
    clock_bridge = Node(package='ros_gz_bridge', executable='parameter_bridge',
                        name='clock_bridge', output='screen',
                        arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'])

    # Robot, şarj istasyonu ve ROS köprüleri. 'world' adını buradan alır:
    # köprü konuları /world/<ad>/... olduğu için .sdf'deki <world name> ile aynı olmalı
    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb4_bringup, 'launch', 'turtlebot4_spawn.launch.py')),
        launch_arguments=[('rviz', LaunchConfiguration('rviz'))])

    return LaunchDescription(ARGUMENTS + [
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', resource_path),
        SetEnvironmentVariable('IGN_GUI_PLUGIN_PATH', gui_plugin_path),
        gazebo,
        clock_bridge,
        spawn,
    ])
