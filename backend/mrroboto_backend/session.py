"""
Orquestador: junta oido + cerebro + voz + ojos y le da intencion al robot.

Dos hilos:
  - Voz:    VAD -> Whisper -> Claude -> ElevenLabs (boca por RMS). Half-duplex:
            el microfono se pausa mientras MrRoboto habla, para no oirse a si mismo.
  - Vision: camara -> reconocerte -> saludar (cara + opcionalmente voz), con
            cooldown para no saludar en bucle.

El backend nunca bloquea por el robot: si el ESP32 no responde, la conversacion
sigue igual, solo que sin cara.
"""

from __future__ import annotations

import re
import threading
import time

from . import tts
from .robot import Robot, VOICE_TAGS

_TAG_RE = re.compile(r"\[[a-zA-Z]+\]")


def split_tags(text: str) -> tuple[str, list[str]]:
    """Separa el texto hablado de las etiquetas [emocion]. Devuelve (texto_limpio, tags)."""
    tags = [t for t in _TAG_RE.findall(text) if t.lower() in VOICE_TAGS]
    clean = _TAG_RE.sub("", text)
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    return clean, tags


class Session:
    def __init__(self, settings: dict, secrets: dict, log_fn=None):
        self.settings = settings
        self.secrets = secrets
        self.log_fn = log_fn or (lambda *a, **k: None)

        r = settings["robot"]
        self.robot = Robot(r["ip"], r["enabled"], r.get("timeout_s", 3.0))

        self.stop_event = threading.Event()
        self.speaking = threading.Event()      # True mientras el robot habla
        self._speak_lock = threading.Lock()
        self._threads: list[threading.Thread] = []

        self.brain = None
        self.listener = None
        self.whisper = None
        self.recognizer = None
        self._last_greet = 0.0

    # --- ciclo de vida --------------------------------------------------

    def start(self) -> None:
        self.stop_event.clear()

        # Voz (si hay key de Anthropic)
        if self.secrets.get("anthropic_api_key"):
            from .llm import Brain
            from .stt import Listener, WhisperSTT
            lc = self.settings["llm"]
            self.brain = Brain(self.secrets["anthropic_api_key"], lc["model"],
                               lc["persona"], lc["max_tokens"], lc["history_turns"])
            self.log("sys", f"Cargando Whisper ({self.settings['stt']['model']})...")
            sc = self.settings["stt"]
            self.whisper = WhisperSTT(sc["model"], sc["device"], sc["compute_type"], sc["language"])
            self.listener = Listener(self.settings["vad"], self.settings["audio"]["input_device"])
            t = threading.Thread(target=self._voice_loop, daemon=True)
            t.start(); self._threads.append(t)
            self.log("sys", "Voz lista. Hablame.")
        else:
            self.log("sys", "Sin key de Anthropic: la voz esta desactivada.")

        # Vision (si esta habilitada)
        if self.settings["vision"]["enabled"]:
            from .vision import FaceRecognizer
            self.recognizer = FaceRecognizer()
            enrolled = self.recognizer.enrolled()
            self.log("sys", f"Vision lista. Caras conocidas: {', '.join(enrolled) or 'ninguna'}.")
            t = threading.Thread(target=self._vision_loop, daemon=True)
            t.start(); self._threads.append(t)

    def stop(self) -> None:
        self.stop_event.set()
        for t in self._threads:
            t.join(timeout=2.0)
        self._threads.clear()
        self.robot.mouth(0.0)
        self.log("sys", "Sesion detenida.")

    def running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    # --- utilidades -----------------------------------------------------

    def log(self, kind: str, text: str) -> None:
        self.log_fn(kind, text)

    def _say(self, text: str) -> None:
        """Habla (con boca) de forma exclusiva; pausa el microfono mientras."""
        clean, tags = split_tags(text)
        for tag in tags:                    # las etiquetas mueven la quimica del robot
            self.robot.voice_tag(tag)
        if not clean:
            return
        with self._speak_lock:
            self.speaking.set()
            try:
                tts.speak(clean, self.settings["tts"], self.secrets, self.robot,
                          self.stop_event, self.settings["audio"]["output_device"])
            except Exception as e:  # noqa: BLE001
                self.log("error", f"TTS: {e}")
            finally:
                self.speaking.clear()

    # --- hilo de voz ----------------------------------------------------

    def _voice_loop(self) -> None:
        should_run = lambda: not self.stop_event.is_set()
        is_paused = lambda: self.speaking.is_set()
        try:
            for pcm in self.listener.utterances(should_run, is_paused):
                if self.stop_event.is_set():
                    break
                text = self.whisper.transcribe(pcm)
                if not text or len(text) < 2:
                    continue
                self.log("user", text)
                self.robot.look(0.0, 0.05)      # atento, mirando al frente
                try:
                    reply = self.brain.reply(text)
                except Exception as e:  # noqa: BLE001
                    self.log("error", f"Claude: {e}")
                    continue
                self.log("robot", reply)
                self._say(reply)
        except Exception as e:  # noqa: BLE001
            self.log("error", f"Voz: {e}")

    # --- hilo de vision -------------------------------------------------

    def _vision_loop(self) -> None:
        import cv2
        from .vision import open_camera

        vc = self.settings["vision"]
        cap = open_camera(vc["camera_index"])
        if not cap.isOpened():
            self.log("error", f"No pude abrir la camara {vc['camera_index']}.")
            return
        try:
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rect = self.recognizer.largest(self.recognizer.detect(gray))
                if rect is None:
                    time.sleep(0.03)
                    continue

                # mira hacia donde esta la cara (x normalizado -1..1)
                cx = rect[0] + rect[2] / 2
                nx = (cx / gray.shape[1]) * 2 - 1
                self.robot.look(-nx, 0.0)       # -nx: la camara ve en espejo

                name, dist = (None, 999.0)
                if vc["recognize"]:
                    name, dist = self.recognizer.recognize(gray, rect)

                known = name is not None and dist <= vc["confidence"]
                now = time.time()
                if known and (now - self._last_greet) > vc["greet_cooldown_s"]:
                    self._last_greet = now
                    self.log("sys", f"Te reconoci: {name} (dist {dist:.0f}).")
                    self.robot.wave()
                    if self.settings["session"]["speak_greeting"] and self.brain and not self.speaking.is_set():
                        threading.Thread(target=self._greet, args=(name,), daemon=True).start()
                time.sleep(0.06)
        except Exception as e:  # noqa: BLE001
            self.log("error", f"Vision: {e}")
        finally:
            cap.release()

    def _greet(self, name: str) -> None:
        try:
            line = self.brain.reply(f"(Acabas de ver y reconocer a {name} frente a la camara. "
                                    f"Saludalo por su nombre, calido y muy breve.)")
            self.log("robot", line)
            self._say(line)
        except Exception as e:  # noqa: BLE001
            self.log("error", f"Saludo: {e}")
