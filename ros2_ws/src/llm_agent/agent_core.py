"""Ajanın çekirdeği (Faz 4.3): Türkçe görev → araç çağrıları → kartın kararı → düzeltme.

ROS'a bağlı değildir: model (chat) ve dünya (Executor) dışarıdan verilir, PC'de sahte
ikisiyle sınanır (tests/test_agent_core.py). ROS bağlantısı agent_node.py'de.

Döngü:
1. Görev ve aracın o anki konumu (ölçüm anıyla) modele verilir.
2. Model bir araç çağırır. Komut, çağrıdan ÖNCE alınan konumu inanç olarak taşır: inancın
   yaşı (CONSISTENCY'nin Δt'si, RULES §3.4) modelin düşünme süresidir.
3. Kartın cevabı (köprünün /guard/feedback metni) araç sonucu olarak modele döner; kabul
   edilen git'te varış, bekle'de süre beklenir.
4. Model araç çağırmadan yazınca görev biter. Görev başına en çok MAX_REJECTIONS ret
   (RULES §5.4: kartın kurtarma sınırı 5'ten küçük olmalı), sonra ajan vazgeçer.

Araç tanımları burada tek kaynaktır (K-045): tools/llm_select_bench.py da buradan okur.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, Tuple

MODEL = "granite4.1:3b"            # K-045
OLLAMA_URL = "http://localhost:11434"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096}   # Faz 5'in kesin değeri ayrı karar
MAX_REJECTIONS = 3                 # RULES §5.4: ≤ 4, seçilen 3
MAX_STEPS = 12                     # model durmazsa güvenlik sınırı (araç çağrısı sayısı)
TIMEOUT_S = 120

SYSTEM = (
    "Sen bir insansız kara aracını (İKA) yöneten görev ajanısın. Kullanıcının Türkçe "
    "talimatını yalnızca verilen araçları çağırarak yerine getir. Her adımda TEK bir araç "
    "çağır ve sonucunu bekle. Yer adı verilmişse 'yer' alanını kullan, koordinat verilmişse "
    "'x' ve 'y' alanlarını (metre) kullan. Bir komut reddedilirse özet YAZMA: gerekçeyi oku "
    "ve hemen düzeltilmiş yeni bir araç çağır; gerekçe bir güvenli nokta ya da konum "
    "söylüyorsa onu kullan, hız sınırı aralık söylüyorsa aralığın içinde bir değer seç. "
    "Görevin bütün adımları bitince araç çağırmadan kısa bir Türkçe özet yaz."
)

Place = Tuple[float, float, float]           # x (m), y (m), varış yönü (rad)


def places_from_site(site: dict) -> Dict[str, Place]:
    """gen_site.load_site() → ajanın yer adları: güvenli noktalar (yön 0; her yönde dönülebilir)
    ve places (kendi yönleriyle). K-044."""
    out = {n: (x / 100, y / 100, 0.0) for n, (x, y) in site["safe"].items()}
    out.update({n: (x / 100, y / 100, yaw / 1000) for n, (x, y, yaw) in site.get("places", {}).items()})
    return out


def tool_definitions(place_names: List[str]) -> List[dict]:
    """Ollama/OpenAI biçiminde araç tanımları."""
    return [
        # Tek araç, yer ve x/y seçenekleri yan yana: ikiye ayrılınca (git_yer / git_koordinat)
        # granite yer adlarını koordinat aracına (0, 0) yazdı, 30/31 → 25/31 (2026-10-14).
        # Model iki alanı birlikte doldurursa tool_call_to_task çözer.
        {"type": "function", "function": {
            "name": "git",
            "description": "Aracı bir hedefe gönder. Ya 'yer' ya da 'x' ile 'y' verilir.",
            "parameters": {"type": "object", "properties": {
                "yer": {"type": "string", "enum": place_names, "description": "Kayıtlı yerin adı"},
                "x": {"type": "number", "description": "Hedefin x koordinatı, metre"},
                "y": {"type": "number", "description": "Hedefin y koordinatı, metre"},
            }},
        }},
        {"type": "function", "function": {
            "name": "bekle",
            "description": ("Olduğun yerde belirtilen süre bekle. Süre SANİYE cinsinden: "
                            "dakika verilirse saniyeye çevir (1 dakika = 60, yarım dakika = 30, "
                            "bir buçuk dakika = 90, iki dakika = 120 saniye)."),
            "parameters": {"type": "object", "required": ["sure_s"], "properties": {
                "sure_s": {"type": "number", "description": "Bekleme süresi, saniye"},
            }},
        }},
        {"type": "function", "function": {
            "name": "hiz_siniri",
            "description": "Aracın en yüksek hızını sınırla.",
            "parameters": {"type": "object", "required": ["deger_mps"], "properties": {
                "deger_mps": {"type": "number", "description": "Hız sınırı, m/s"},
            }},
        }},
        {"type": "function", "function": {
            "name": "dur",
            "description": "Aracı hemen durdur.",
            "parameters": {"type": "object", "properties": {}},
        }},
    ]


@dataclass
class Observation:
    x: float          # m, harita çerçevesi
    y: float
    stamp: float      # ROS zamanı, s: konumun okunduğu an


class Executor(Protocol):
    def observe(self) -> Observation: ...

    def execute(self, task: dict) -> Tuple[bool, str]:
        """Görevi /guard/task'a gönderir, kartın kararını bekler; kabul edilen git'te
        varışı, bekle'de süreyi bekler. (kabul, modele dönecek metin)."""
        ...


class ToolError(ValueError):
    """Model geçersiz bir araç çağırdı: karta gitmez, hata metni modele döner."""


def _num(args: dict, key: str) -> float:
    v = args.get(key)
    try:
        v = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        raise ToolError(f"'{key}' sayı olmalı") from None
    if not math.isfinite(v):
        raise ToolError(f"'{key}' sayı olmalı")
    return v


FILLER_TOL_M = 0.5


def _filler_xy(x: float, y: float, belief: Observation) -> bool:
    """yer ile birlikte gelen koordinat dolgu mu: (0, 0) ya da aracın o anki konumu (modeller
    bağlamdaki konumu kopyalıyor). Kayıtlarda görülen biçimler (2026-10-14)."""
    return (x, y) == (0.0, 0.0) or math.hypot(x - belief.x, y - belief.y) <= FILLER_TOL_M


def tool_call_to_task(name: str, args: dict, places: Dict[str, Place], belief: Observation,
                      task_id: str) -> dict:
    """Modelin araç çağrısı → /guard/task JSON'u (K-050)."""
    b = {"x": belief.x, "y": belief.y, "stamp": belief.stamp}
    if name == "git":
        yer = args.get("yer")
        has_xy = args.get("x") is not None and args.get("y") is not None
        if yer and has_xy and not _filler_xy(_num(args, "x"), _num(args, "y"), belief):
            raise ToolError("ya 'yer' ya da 'x' ile 'y' ver, ikisini birden verdin")
        if yer:
            if yer not in places:
                raise ToolError(f"'{yer}' kayıtlı bir yer değil")
            x, y, yaw = places[yer]
            # "yer" köprüye gitmez (K-050 biçimi), kayıt ve varış metni için
            return {"id": task_id, "cmd": "git", "x": x, "y": y, "yaw": yaw, "yer": yer, "belief": b}
        return {"id": task_id, "cmd": "git", "x": _num(args, "x"), "y": _num(args, "y"),
                "yaw": 0.0, "belief": b}
    if name == "bekle":
        return {"id": task_id, "cmd": "bekle", "sure_s": _num(args, "sure_s"), "belief": b}
    if name == "hiz_siniri":
        return {"id": task_id, "cmd": "hiz_siniri", "deger_mps": _num(args, "deger_mps"), "belief": b}
    if name == "dur":
        return {"id": task_id, "cmd": "dur"}
    raise ToolError(f"'{name}' diye bir araç yok (araçlar: git, bekle, hiz_siniri, dur)")


def _pos(o: Observation) -> str:
    return f"({o.x:.2f}; {o.y:.2f})".replace(".", ",")


def ollama_chat(model: str = MODEL, options: Optional[dict] = None,
                url: str = OLLAMA_URL) -> Callable[[List[dict], List[dict]], dict]:
    """Ollama /api/chat'e bağlı chat(messages, tools) → message."""
    import requests                     # yalnız gerçek modelde gerekir

    opts = dict(OPTIONS if options is None else options)

    def chat(messages: List[dict], tools: List[dict]) -> dict:
        body = {"model": model, "stream": False, "options": opts, "tools": tools,
                "messages": messages}
        r = requests.post(f"{url}/api/chat", json=body, timeout=TIMEOUT_S)
        r.raise_for_status()
        return r.json()["message"]

    return chat


class Agent:
    def __init__(self, chat: Callable[[List[dict], List[dict]], dict], executor: Executor,
                 places: Dict[str, Place], *, max_rejections: int = MAX_REJECTIONS,
                 max_steps: int = MAX_STEPS, log: Callable[[dict], None] = lambda e: None) -> None:
        self.chat = chat
        self.executor = executor
        self.places = places
        self.tools = tool_definitions(sorted(places))
        self.max_rejections = max_rejections
        self.max_steps = max_steps
        self.log = log
        self.runs = 0

    def run(self, text: str) -> dict:
        """Bir görevi baştan sona yürütür. Dönen özet: status (bitti / vazgeçti / adım sınırı),
        summary (modelin son metni), steps, rejections."""
        self.runs += 1
        obs = self.executor.observe()
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"{text}\n\nAracın şu anki konumu: {_pos(obs)} m."}]
        steps = rejections = 0
        self.log({"event": "görev", "text": text, "pos": [obs.x, obs.y]})
        while True:
            t0 = time.monotonic()
            msg = self.chat(messages, self.tools)
            llm_s = time.monotonic() - t0
            calls = msg.get("tool_calls") or []
            if not calls:
                summary = msg.get("content", "").strip()
                self.log({"event": "bitti", "summary": summary, "llm_s": llm_s})
                return {"status": "bitti", "summary": summary, "steps": steps, "rejections": rejections}
            fn = calls[0]["function"]                  # her adımda tek araç (SYSTEM)
            name, args = fn.get("name", ""), fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            steps += 1
            task_id = f"r{self.runs}s{steps}"
            try:
                task = tool_call_to_task(name, args, self.places, obs, task_id)
                accepted, result = self.executor.execute(task)
                if not accepted:
                    rejections += 1
            except ToolError as e:
                task, accepted, result = None, False, f"Araç çağrısı geçersiz: {e}. Karta gönderilmedi."
            obs = self.executor.observe()              # sonraki çağrının inancı bu konum
            result_text = f"{result} Aracın şu anki konumu: {_pos(obs)} m."
            self.log({"event": "adım", "id": task_id, "tool": name, "args": args, "task": task,
                      "accepted": accepted, "result": result, "llm_s": llm_s})
            messages.append({"role": "assistant", "content": msg.get("content", ""),
                             "tool_calls": [{"function": {"name": name, "arguments": args}}]})
            messages.append({"role": "tool", "tool_name": name, "content": result_text})
            if rejections >= self.max_rejections:
                self.log({"event": "vazgeçti", "rejections": rejections})
                return {"status": "vazgeçti", "summary": result, "steps": steps,
                        "rejections": rejections}
            if steps >= self.max_steps:
                self.log({"event": "adım sınırı", "steps": steps})
                return {"status": "adım sınırı", "summary": result, "steps": steps,
                        "rejections": rejections}
