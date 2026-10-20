"""Köprüyü başlatır. Kartlı (varsayılan): agent_bridge (ajan kanalı) ve vehicle_bridge (araç
kanalı). Kartsız (guard:=false, A/B, K-054): direct_bridge.

Kullanım (depo kökünden; kart bağlı, simülasyon ve navigation.launch.py açıkken):
    ros2 launch ros2_ws/src/guard_bridge/launch/bridge.launch.py
    ros2 launch ros2_ws/src/guard_bridge/launch/bridge.launch.py feedback:=minimal   # C
    ros2 launch ros2_ws/src/guard_bridge/launch/bridge.launch.py guard:=false        # A/B

Kart açılışta HOLD'dadır. NORMAL'e almak için:
    ros2 service call /guard/reset std_srvs/srv/Trigger
Kartın kararları:
    ros2 topic echo /guard/verdict

Düğümler düz betiktir (colcon paketi değil), python3 ile çalıştırılır. İki ayrı
düğüm (K-040 karar 2): deney yapılandırmalarında yalnız ajan tarafı değişir.
Hangi yapılandırmada ne açık: experiments/launch/experiment.launch.py.
"""
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration

BRIDGE_DIR = Path(__file__).resolve().parent.parent

ARGUMENTS = [
    DeclareLaunchArgument('guard', default_value='true', choices=['true', 'false'],
                          description='false: kart yolda değil, direct_bridge (A/B)'),
    DeclareLaunchArgument('feedback', default_value='full', choices=['full', 'minimal'],
                          description='ajanın gördüğü ret metni: full (D) ya da minimal (C)'),
]


def bridge(script, *params):
    args = ['-p', 'use_sim_time:=true'] + [a for p in params for a in ('-p', p)]
    return ExecuteProcess(cmd=['python3', str(BRIDGE_DIR / script), '--ros-args', *args],
                          output='screen', sigterm_timeout='3')


def setup(context):
    if LaunchConfiguration('guard').perform(context) == 'false':
        return [bridge('direct_bridge.py')]
    feedback = LaunchConfiguration('feedback').perform(context)
    return [bridge('vehicle_bridge.py'), bridge('agent_bridge.py', f'feedback:={feedback}')]


def generate_launch_description():
    return LaunchDescription(ARGUMENTS + [OpaqueFunction(function=setup)])
