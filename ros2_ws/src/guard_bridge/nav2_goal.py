"""Nav2'deki tek hedef: gönder ve iptal et (K-042). vehicle_bridge (kartlı) ve direct_bridge
(kartsız, A/B) ortak kullanır: Nav2'ye hedef iki yapılandırmada da aynı yoldan gider.

Yeni hedef eskisinin yerine geçer. Gönderim ile kabul arasında iptal istenebilir: her hedefin
bir sırası var, kabul geldiğinde sırası iptal edilmişse hemen iptal edilir.
"""
from __future__ import annotations

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node


class Nav2Goal:
    def __init__(self, node: Node) -> None:
        self.node = node
        self.client = ActionClient(node, NavigateToPose, "navigate_to_pose")
        self.handle = None
        self.gen = 0
        self.cancelled_gen = 0

    def ready(self) -> bool:
        return self.client.server_is_ready()

    def send(self, x: float, y: float, qz: float, qw: float) -> None:
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.node.get_clock().now().to_msg()
        goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
        goal.pose.pose.orientation.z, goal.pose.pose.orientation.w = qz, qw
        self.gen += 1
        gen = self.gen
        self.client.send_goal_async(goal).add_done_callback(lambda fut: self._response(gen, fut))

    def _response(self, gen: int, fut) -> None:
        handle = fut.result()
        if handle is None or not handle.accepted:
            return
        if gen <= self.cancelled_gen:            # kabul gelmeden iptal istenmişti
            handle.cancel_goal_async()
            return
        if gen == self.gen:                      # daha yeni bir hedef gönderilmediyse
            self.handle = handle

    def cancel(self, why: str) -> None:
        """Nav2'nin hedefini iptal et (yoksa ya da bitmişse zararsız)."""
        self.cancelled_gen = self.gen
        if self.handle is not None:
            self.handle.cancel_goal_async()
            self.handle = None
            self.node.get_logger().info(f"Nav2 hedefi iptal: {why}")
