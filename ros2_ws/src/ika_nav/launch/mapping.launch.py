"""İKA ile sahanın haritasını çıkarır: RTAB-Map, kamera + lidar (Faz 3.1, K-033).

Kullanım (depo kökünden, simülasyon açıkken):
    ros2 launch ros2_ws/src/ika_nav/launch/mapping.launch.py

Haritayı kaydetmek (gezdirme bitince, bu dosya çalışırken):
    ros2 run nav2_map_server map_saver_cli -f ros2_ws/src/ika_nav/maps/ika_saha \\
        -t /rtabmap/map --ros-args -p use_sim_time:=true

RTAB-Map konularını kendi ad alanına koyar: 2B harita /map değil /rtabmap/map.

RTAB-Map'in hazır rtabmap.launch.py'si bizim konu adlarımız ve ayarlarımızla çağrılır.
Görevler: kamera yer tanır (döngü kapatma), lidar 2B haritayı çizer ve düğümler
arasındaki konumu hesaplar, tekerlek odometrisi ilk tahmini verir.
Veritabanı (~/.ros/ika_saha.db) görüntüleri içerir, büyüktür; depoya girmez.
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

# RTAB-Map parametreleri (varsayılandan değiştirilenler)
RTABMAP_PARAMS = {
    'Grid/Sensor': '0',                   # 2B harita lidardan (1 = derinlik görüntüsü)
    'Grid/RangeMax': '8',                 # lidarın menzili, m (varsayılan 5)
    'Reg/Strategy': '1',                  # düğümler arası konum: ICP, lidar taramaları üst üste
    'RGBD/NeighborLinkRefining': 'true',  # her odometri adımını lidarla düzelt (patinaj, dönüş hatası)
    'Reg/Force3DoF': 'true',              # zemin düz: yalnızca x, y, yön
}


def generate_launch_description():
    rtabmap_args = ' '.join(f'--{k} {v}' for k, v in RTABMAP_PARAMS.items())
    rtabmap_args += ' --delete_db_on_start'   # her çalıştırmada temiz harita

    rtabmap = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(
            Path(get_package_share_directory('rtabmap_launch')) / 'launch' / 'rtabmap.launch.py')),
        launch_arguments={
            'use_sim_time': 'true',
            'frame_id': 'base_link',
            'odom_topic': '/odom',
            'visual_odometry': 'false',       # tekerlek odometrisi kullanılır
            'rgb_topic': '/camera/image',
            'depth_topic': '/camera/depth_image',
            'camera_info_topic': '/camera/camera_info',
            'subscribe_scan': 'true',
            'scan_topic': '/scan',
            'approx_sync': 'true',            # kamera ve lidar damgaları birebir aynı değil
            'database_path': '~/.ros/ika_saha.db',
            'rtabmap_args': rtabmap_args,
            'rtabmap_viz': 'true',            # döngü kapanmalarını canlı gösterir
            'rviz': 'false',
        }.items())

    return LaunchDescription([rtabmap])
