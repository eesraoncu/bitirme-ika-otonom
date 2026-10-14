"""İKA'yı Nav2 ile hedefe götürür: AMCL + kayıtlı harita + keepout maskesi (Faz 3.2b, K-037).

Kullanım (depo kökünden, simülasyon açıkken, RTAB-Map KAPALIYKEN):
    ros2 launch ros2_ws/src/ika_nav/launch/navigation.launch.py

Hedef: RViz'de "2D Goal Pose". Ayarlar config/nav2_params.yaml'da.

İki grup düğüm, her biri kendi lifecycle_manager'ıyla sırayla açılır:
- konum: map_server (ika_saha.pgm), amcl, filter_mask_server (keepout maskesi;
  costmap'lerde şişirmeden önce bir katman olarak okunur)
- gezinme: planner_server, controller_server, behavior_server, bt_navigator,
  velocity_smoother, collision_monitor
Nav2 karttan geçmeden süremez (K-040 karar 1): bt_navigator RViz'in /goal_pose'unu
dinlemez, hedefi köprü kartın onayıyla NavigateToPose olarak verir; hız komutları
/cmd_vel yerine /cmd_vel_raw → velocity_smoother (K-046) → /cmd_vel_smoothed →
collision_monitor (K-041) → /cmd_vel_nav'a gider,
/cmd_vel'e yalnız köprünün araç tarafı yazar.
Köprüyü ayrıca başlatın: ros2_ws/src/guard_bridge/launch/bridge.launch.py
"""
from pathlib import Path

from launch import LaunchDescription
from launch_ros.actions import Node

PKG_DIR = Path(__file__).resolve().parent.parent
PARAMS = str(PKG_DIR / 'config' / 'nav2_params.yaml')
MAP = str(PKG_DIR / 'maps' / 'ika_saha.yaml')
KEEPOUT = str(PKG_DIR / 'maps' / 'ika_saha_keepout.yaml')   # tools/gen_site.py üretir

LOCALIZATION = ['map_server', 'amcl', 'filter_mask_server']
NAVIGATION = ['planner_server', 'controller_server', 'behavior_server', 'bt_navigator',
              'velocity_smoother', 'collision_monitor']


# K-040 karar 1: Nav2'nin karta uğramadan kullanabileceği yol kalmasın
TO_GUARD = {
    'bt_navigator': [('goal_pose', '/goal_pose_unused')],
    # Hız önce yumuşatıcıdan (K-046), sonra Nav2'nin çarpışma bekçisinden geçer (K-041):
    # /cmd_vel_raw → /cmd_vel_smoothed → /cmd_vel_nav
    'controller_server': [('cmd_vel', '/cmd_vel_raw')],
    'behavior_server': [('cmd_vel', '/cmd_vel_raw')],
    'velocity_smoother': [('cmd_vel', '/cmd_vel_raw'), ('cmd_vel_smoothed', '/cmd_vel_smoothed')],
}


def nav2_node(package, executable, name, extra=None):
    params = [PARAMS] + ([extra] if extra else [])
    return Node(package=package, executable=executable, name=name,
                output='screen', parameters=params, remappings=TO_GUARD.get(name, []))


def lifecycle_manager(name, nodes):
    return Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
                name=name, output='screen',
                parameters=[{'use_sim_time': True, 'autostart': True, 'node_names': nodes}])


def generate_launch_description():
    return LaunchDescription([
        # konum
        nav2_node('nav2_map_server', 'map_server', 'map_server', {'yaml_filename': MAP}),
        nav2_node('nav2_amcl', 'amcl', 'amcl'),
        nav2_node('nav2_map_server', 'map_server', 'filter_mask_server', {'yaml_filename': KEEPOUT}),
        lifecycle_manager('lifecycle_manager_localization', LOCALIZATION),
        # gezinme
        nav2_node('nav2_planner', 'planner_server', 'planner_server'),
        nav2_node('nav2_controller', 'controller_server', 'controller_server'),
        nav2_node('nav2_behaviors', 'behavior_server', 'behavior_server'),
        nav2_node('nav2_bt_navigator', 'bt_navigator', 'bt_navigator'),
        nav2_node('nav2_velocity_smoother', 'velocity_smoother', 'velocity_smoother'),
        nav2_node('nav2_collision_monitor', 'collision_monitor', 'collision_monitor'),
        lifecycle_manager('lifecycle_manager_navigation', NAVIGATION),
    ])
