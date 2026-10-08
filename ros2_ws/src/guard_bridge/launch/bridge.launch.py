"""Köprünün iki tarafını başlatır: agent_bridge (ajan kanalı) ve vehicle_bridge (araç kanalı).

Kullanım (depo kökünden; kart bağlı, simülasyon ve navigation.launch.py açıkken):
    ros2 launch ros2_ws/src/guard_bridge/launch/bridge.launch.py

Kart açılışta HOLD'dadır. NORMAL'e almak için:
    ros2 service call /guard/reset std_srvs/srv/Trigger
Kartın kararları:
    ros2 topic echo /guard/verdict

Düğümler düz betiktir (colcon paketi değil), python3 ile çalıştırılır. İki ayrı
düğüm (K-040 karar 2): deney yapılandırmalarında yalnız ajan tarafı değişir.
"""
from pathlib import Path

from launch import LaunchDescription
from launch.actions import ExecuteProcess

BRIDGE_DIR = Path(__file__).resolve().parent.parent


def bridge(script):
    return ExecuteProcess(
        cmd=['python3', str(BRIDGE_DIR / script), '--ros-args', '-p', 'use_sim_time:=true'],
        output='screen', sigterm_timeout='3')


def generate_launch_description():
    return LaunchDescription([
        bridge('vehicle_bridge.py'),
        bridge('agent_bridge.py'),
    ])
