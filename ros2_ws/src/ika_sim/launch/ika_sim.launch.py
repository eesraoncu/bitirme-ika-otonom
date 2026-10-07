"""İKA deney sahasını İKA aracıyla açar (Faz 3, K-034).

Kullanım (depo kökünden):
    ros2 launch ros2_ws/src/ika_sim/launch/ika_sim.launch.py

Araç dünyanın içinde (ika_saha.sdf'nin sonunda <include>). Bu dosya üç şey yapar:
Gazebo'yu açar (dünya ve model arama yoluna worlds/ ile models/ eklenir), ROS
köprüsünü config/bridge.yaml ile başlatır ve aracın sabit tf'lerini yayınlar.
"""
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

PKG_DIR = Path(__file__).resolve().parent.parent
WORLDS_DIR = PKG_DIR / 'worlds'
MODELS_DIR = PKG_DIR / 'models'
BRIDGE_CONFIG = PKG_DIR / 'config' / 'bridge.yaml'

# Aracın sabit dönüşümleri: (ebeveyn, çocuk, x, y, z, roll, pitch, yaw).
# Konumlar models/ika_arac/model.sdf'deki <link> pozlarıyla aynı olmalı (lidar_link,
# imu_link, camera_link). camera_optical_frame: görüntü eksenleri (z ileri, x sağa,
# y aşağı); kameranın görüntüleri bu çerçeveyle etiketli (model.sdf, değişiklik 4).
# odom → base_link bunlardan değil, köprüden gelir (DiffDrive, /tf)
STATIC_TFS = [
    ('base_link', 'lidar_link', 0.0, 0.0, 0.34, 0.0, 0.0, 0.0),
    ('base_link', 'imu_link', 0.0, 0.0, 0.05, 0.0, 0.0, 0.0),
    ('base_link', 'camera_link', 0.58, 0.0, 0.05, 0.0, 0.0, 0.0),
    ('camera_link', 'camera_optical_frame', 0.0, 0.0, 0.0, -1.5708, 0.0, -1.5708),
]

ARGUMENTS = [
    DeclareLaunchArgument('world', default_value='ika_saha',
                          description='worlds/ altındaki dünya, uzantısız'),
]


def static_tf(parent, child, x, y, z, roll, pitch, yaw):
    # use_sim_time: damga sim saatinden olsun (yoksa bilgisayar saati, tf2_monitor'de
    # −1,79 milyar s "gecikme" görünüyordu)
    return Node(package='tf2_ros', executable='static_transform_publisher',
                name=f'tf_{child}', output='log', parameters=[{'use_sim_time': True}],
                arguments=['--x', str(x), '--y', str(y), '--z', str(z),
                           '--roll', str(roll), '--pitch', str(pitch), '--yaw', str(yaw),
                           '--frame-id', parent, '--child-frame-id', child])


def generate_launch_description():
    # Gazebo dünyayı worlds/'te, araç modelini (model://ika_arac) models/'te arar.
    # Fuel modelleri (bariyer, kamyonet...) adresle gelir, yola gerekmez
    resource_path = ':'.join([str(WORLDS_DIR), str(MODELS_DIR)])

    # -r: açılır açılmaz çalıştır. -v 4: ayrıntılı günlük
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(
            Path(get_package_share_directory('ros_gz_sim')) / 'launch' / 'gz_sim.launch.py')),
        launch_arguments=[('gz_args', [LaunchConfiguration('world'), '.sdf -r -v 4'])])

    # Konu listesi ve yönleri config/bridge.yaml'da
    bridge = Node(package='ros_gz_bridge', executable='parameter_bridge',
                  name='ika_bridge', output='screen',
                  parameters=[{'config_file': str(BRIDGE_CONFIG)}])

    return LaunchDescription(ARGUMENTS + [
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', resource_path),
        gazebo,
        bridge,
        *[static_tf(*t) for t in STATIC_TFS],
    ])
