#!/usr/bin/env python3
"""Ajanın ROS bağlantısı (Faz 4.3): /agent/task → agent_core → /guard/task … /guard/feedback.

Kullanım (depo kökünden; simülasyon, Nav2, köprü açık; Ollama çalışıyor; kart NORMAL'de):
    python3 ros2_ws/src/llm_agent/agent_node.py --ros-args -p use_sim_time:=true
    ros2 topic pub --once /agent/task std_msgs/String "data: 'Kapı önüne git, orada 30 saniye bekle'"

- /agent/task (std_msgs/String): Türkçe görev. Görev sürerken gelen yenisi reddedilir.
- Konum: map → base_link (TF), okunduğu an ROS zamanı: komutların inancı (K-050).
- /guard/task'a yazar, /guard/feedback'ten id ile kararı okur (köprü, K-050).
- Kabul edilen git'te Nav2'nin NavigateToPose sonucu beklenir; bekle'de süre beklenir.
- /agent/log (std_msgs/String, JSON satırı): her olay (ayarlar, görev, adım, bitiş). Faz 5'in
  kaydının hammaddesi.
Parametreler: model, temperature, seed (agent_core varsayılanları; ayarlar günlüğe yazılır).
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import rclpy
from action_msgs.msg import GoalStatus, GoalStatusArray
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_action_status_default
from rclpy.time import Time
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import agent_core as ac  # noqa: E402
import gen_site as gs  # noqa: E402

FEEDBACK_WAIT_S = 3.0        # kartın kararı (VERDICT ≤ 0,5 s) + köprü
GOAL_APPEAR_S = 10.0         # kabul edilen git'in Nav2'de görünmesi
GOAL_TIMEOUT_S = 240.0       # varış
TERMINAL = {GoalStatus.STATUS_SUCCEEDED: "vardı", GoalStatus.STATUS_CANCELED: "iptal edildi",
            GoalStatus.STATUS_ABORTED: "vazgeçti"}


class RosWorld:
    """agent_core.Executor: ROS üzerinden gözlem ve yürütme. Bekleyen çağrılar ajan iş
    parçacığında; geri çağrılar yürütücünün iş parçacığında."""

    def __init__(self, node: Node) -> None:
        self.node = node
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, node)
        self.task_pub = node.create_publisher(String, "/guard/task", 10)
        self.feedback: Dict[str, dict] = {}
        self.status: Dict[bytes, int] = {}
        self.lock = threading.Lock()
        node.create_subscription(String, "/guard/feedback", self.on_feedback, 10)
        node.create_subscription(GoalStatusArray, "/navigate_to_pose/_action/status",
                                 self.on_status, qos_profile_action_status_default)

    def on_feedback(self, msg: String) -> None:
        fb = json.loads(msg.data)
        with self.lock:
            self.feedback[fb.get("id", "")] = fb

    def on_status(self, msg: GoalStatusArray) -> None:
        with self.lock:
            for s in msg.status_list:
                self.status[bytes(s.goal_info.goal_id.uuid)] = s.status

    def observe(self) -> ac.Observation:
        end = time.monotonic() + 2.0
        while True:
            try:
                t = self.tf.lookup_transform("map", "base_link", Time()).transform.translation
                return ac.Observation(t.x, t.y, self.node.get_clock().now().nanoseconds / 1e9)
            except TransformException:
                if time.monotonic() > end:
                    raise
                time.sleep(0.05)

    def _wait(self, cond, seconds: float):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            with self.lock:
                got = cond()
            if got is not None:
                return got
            time.sleep(0.05)
        return None

    def execute(self, task: dict) -> Tuple[bool, str]:
        with self.lock:
            known = set(self.status)
            self.feedback.pop(task["id"], None)
        self.task_pub.publish(String(data=json.dumps(task, ensure_ascii=False)))
        fb = self._wait(lambda: self.feedback.get(task["id"]), FEEDBACK_WAIT_S)
        if fb is None:
            return False, "Kartın kararı gelmedi (köprü çalışmıyor olabilir)."
        if not fb["accepted"]:
            return False, fb["text"]
        cmd = task["cmd"]
        if cmd == "git":
            target = f"({task['x']:.2f}; {task['y']:.2f})".replace(".", ",")
            if task.get("yer"):
                target = f"{task['yer']} {target}"
            return True, f"{fb['text']} {self._arrival(known, target)}"
        if cmd == "bekle":
            time.sleep(task["sure_s"])
            return True, f"{fb['text']} {task['sure_s']:g} saniye beklendi."
        if cmd == "hiz_siniri":
            return True, f"{fb['text']} Hız sınırı {task['deger_mps']:g} m/s yapıldı."
        return True, f"{fb['text']} Araç durduruldu."

    def _arrival(self, known, target: str) -> str:
        new = lambda: [s for g, s in self.status.items() if g not in known] or None  # noqa: E731
        if self._wait(new, GOAL_APPEAR_S) is None:
            return f"Ancak hedef ({target}) Nav2'ye ulaşmadı."
        done = self._wait(lambda: next((TERMINAL[s] for s in (new() or []) if s in TERMINAL), None),
                          GOAL_TIMEOUT_S)
        if done == "vardı":
            return f"Hedefe varıldı: {target}."
        return f"Araç hedefe varamadı: {target} (Nav2: {done or 'zaman aşımı'})."


class AgentNode(Node):
    def __init__(self) -> None:
        super().__init__("llm_agent")
        model = self.declare_parameter("model", ac.MODEL).value
        options = dict(ac.OPTIONS,
                       temperature=float(self.declare_parameter("temperature",
                                                                float(ac.OPTIONS["temperature"])).value),
                       seed=int(self.declare_parameter("seed", ac.OPTIONS["seed"]).value))
        self.log_pub = self.create_publisher(String, "/agent/log", 10)
        self.world = RosWorld(self)
        places = ac.places_from_site(gs.load_site())
        self.agent = ac.Agent(ac.ollama_chat(model, options), self.world, places, log=self.log)
        self.busy = threading.Lock()
        self.create_subscription(String, "/agent/task", self.on_task, 10)
        self.log({"event": "ayarlar", "model": model, "options": options,
                  "max_rejections": ac.MAX_REJECTIONS, "places": sorted(places)})

    def log(self, event: dict) -> None:
        event = {"t": round(self.get_clock().now().nanoseconds / 1e9, 3), **event}
        line = json.dumps(event, ensure_ascii=False)
        self.log_pub.publish(String(data=line))
        self.get_logger().info(line)

    def on_task(self, msg: String) -> None:
        if not self.busy.acquire(blocking=False):
            self.log({"event": "meşgul", "text": msg.data})
            return
        threading.Thread(target=self.run_task, args=(msg.data,), daemon=True).start()

    def run_task(self, text: str) -> None:
        try:
            self.log({"event": "sonuç", **self.agent.run(text)})
        except Exception as e:                      # model ya da TF hatası: ajan çökmesin
            self.log({"event": "hata", "error": f"{type(e).__name__}: {e}"})
        finally:
            self.busy.release()


def main() -> int:
    rclpy.init()
    node = AgentNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
