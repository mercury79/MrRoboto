"""
Panel de control (FastAPI). Sirve la UI web y expone la API para:
  - configurar opciones y GUARDARLAS de forma permanente,
  - meter / verificar / guardar API keys (local, fuera de git),
  - probar el robot, enrolar tu cara, y arrancar/parar la sesion (voz + vision),
  - ver el log/transcripcion en vivo.

Arranca con run.bat. El panel abre en http://127.0.0.1:8080
"""

from __future__ import annotations

import importlib.util
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config as cfg
from . import llm, tts
from .robot import Robot
from .session import Session

app = FastAPI(title="MrRoboto Backend")

# --- estado global del panel ---
_state = {
    "settings": cfg.load_settings(),
    "secrets": cfg.load_secrets(),
    "session": None,        # type: Session | None
}
_log: list[dict] = []
_log_lock = threading.Lock()


def add_log(kind: str, text: str) -> None:
    with _log_lock:
        _log.append({"i": len(_log), "t": time.strftime("%H:%M:%S"), "kind": kind, "text": text})
        if len(_log) > 500:
            del _log[:100]


# ----------------------------------------------------------------------
# Dependencias opcionales (para que el panel avise que falta)
# ----------------------------------------------------------------------

_OPTIONAL = {
    "sounddevice": "Audio (micro/bocina)",
    "numpy": "Audio/vision",
    "faster_whisper": "STT (Whisper)",
    "webrtcvad": "VAD (deteccion de voz)",
    "elevenlabs": "TTS de pago",
    "pyttsx3": "TTS gratis",
    "cv2": "Vision (OpenCV)",
    "anthropic": "Cerebro (Claude)",
}


def _deps() -> dict:
    out = {}
    for mod, desc in _OPTIONAL.items():
        out[mod] = {"installed": importlib.util.find_spec(mod) is not None, "desc": desc}
    return out


# ----------------------------------------------------------------------
# UI estatica
# ----------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(cfg.WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(cfg.WEB_DIR / "index.html"))


# ----------------------------------------------------------------------
# Estado / configuracion
# ----------------------------------------------------------------------

@app.get("/api/status")
def status():
    sess: Session | None = _state["session"]
    robot_cfg = _state["settings"]["robot"]
    robot = Robot(robot_cfg["ip"], robot_cfg["enabled"], 1.5)
    enrolled = []
    spec = importlib.util.find_spec("cv2")
    if spec is not None:
        try:
            from .vision import FaceRecognizer
            enrolled = FaceRecognizer().enrolled()
        except Exception:  # noqa: BLE001
            enrolled = []
    return {
        "running": bool(sess and sess.running()),
        "robot_reachable": robot.reachable(),
        "robot_ip": robot_cfg["ip"],
        "deps": _deps(),
        "secrets": cfg.secret_status(),
        "enrolled": enrolled,
        "models": llm.MODELS,
    }


@app.get("/api/config")
def get_config():
    return {"settings": _state["settings"], "secrets": cfg.secret_status()}


@app.post("/api/config")
async def set_config(req: Request):
    data = await req.json()
    merged = cfg.save_settings(data.get("settings", data))
    _state["settings"] = merged
    add_log("sys", "Preferencias guardadas.")
    return {"ok": True, "settings": merged}


# ----------------------------------------------------------------------
# API keys
# ----------------------------------------------------------------------

@app.post("/api/keys")
async def save_keys(req: Request):
    data = await req.json()
    cfg.save_secrets({
        "anthropic_api_key": data.get("anthropic_api_key"),
        "elevenlabs_api_key": data.get("elevenlabs_api_key"),
    })
    _state["secrets"] = cfg.load_secrets()
    add_log("sys", "API keys guardadas (local, fuera de git).")
    return {"ok": True, "secrets": cfg.secret_status()}


@app.post("/api/keys/verify")
async def verify_keys(req: Request):
    data = await req.json()
    s = _state["secrets"]
    ak = (data.get("anthropic_api_key") or s.get("anthropic_api_key") or "")
    ek = (data.get("elevenlabs_api_key") or s.get("elevenlabs_api_key") or "")
    a_ok, a_msg = llm.verify_key(ak)
    e_ok, e_msg = tts.verify_key(ek) if ek else (False, "No hay key de ElevenLabs (opcional).")
    return {"anthropic": {"ok": a_ok, "msg": a_msg},
            "elevenlabs": {"ok": e_ok, "msg": e_msg}}


@app.get("/api/voices")
def voices():
    ek = _state["secrets"].get("elevenlabs_api_key", "")
    return {"voices": tts.list_voices(ek) if ek else []}


# ----------------------------------------------------------------------
# Robot
# ----------------------------------------------------------------------

@app.post("/api/robot/test")
def robot_test():
    rc = _state["settings"]["robot"]
    robot = Robot(rc["ip"], True, 3.0)
    st = robot.status()
    if st is None:
        add_log("error", f"El robot no responde en {rc['ip']}.")
        return {"ok": False, "error": "sin respuesta"}
    robot.wave()
    add_log("sys", f"Robot OK en {rc['ip']}: {st}")
    return {"ok": True, "status": st}


# ----------------------------------------------------------------------
# Prueba de texto (cerebro + opcionalmente voz)
# ----------------------------------------------------------------------

@app.post("/api/llm/say")
async def llm_say(req: Request):
    data = await req.json()
    text = (data.get("text") or "").strip()
    speak = bool(data.get("speak"))
    if not text:
        return {"ok": False, "error": "texto vacio"}
    ak = _state["secrets"].get("anthropic_api_key", "")
    if not ak:
        return {"ok": False, "error": "falta la key de Anthropic"}
    lc = _state["settings"]["llm"]
    try:
        brain = llm.Brain(ak, lc["model"], lc["persona"], lc["max_tokens"], 4)
        reply = brain.reply(text)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    add_log("user", text)
    add_log("robot", reply)
    if speak:
        rc = _state["settings"]["robot"]
        robot = Robot(rc["ip"], rc["enabled"], rc.get("timeout_s", 3.0))
        try:
            from .session import split_tags
            clean, tags = split_tags(reply)
            for t in tags:
                robot.voice_tag(t)
            tts.speak(clean, _state["settings"]["tts"], _state["secrets"], robot)
        except Exception as e:  # noqa: BLE001
            return {"ok": True, "reply": reply, "tts_error": str(e)}
    return {"ok": True, "reply": reply}


# ----------------------------------------------------------------------
# Vision: enrolar tu cara
# ----------------------------------------------------------------------

@app.post("/api/vision/enroll")
async def enroll(req: Request):
    data = await req.json()
    name = (data.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "falta el nombre"}
    sess: Session | None = _state["session"]
    if sess and sess.running():
        return {"ok": False, "error": "Detén la sesión primero (la cámara está en uso)."}
    if importlib.util.find_spec("cv2") is None:
        return {"ok": False, "error": "Falta OpenCV (instala dependencias completas)."}
    from .vision import FaceRecognizer
    rec = FaceRecognizer()
    cam = _state["settings"]["vision"]["camera_index"]
    add_log("sys", f"Enrolando a {name}... mira a la cámara.")
    res = rec.enroll_from_camera(name, cam, samples=30,
                                 on_progress=lambda c, n: None)
    if res.get("ok"):
        add_log("sys", f"Enrolado {name}: {res['captured']} fotos. Conocidas: {', '.join(res['people'])}.")
    else:
        add_log("error", f"Enrolamiento: {res.get('error')}")
    return res


# ----------------------------------------------------------------------
# Sesion (voz + vision)
# ----------------------------------------------------------------------

@app.post("/api/session/start")
def session_start():
    sess: Session | None = _state["session"]
    if sess and sess.running():
        return {"ok": False, "error": "ya está corriendo"}
    _state["settings"] = cfg.load_settings()
    _state["secrets"] = cfg.load_secrets()
    sess = Session(_state["settings"], _state["secrets"], log_fn=add_log)
    _state["session"] = sess
    try:
        sess.start()
    except Exception as e:  # noqa: BLE001
        add_log("error", f"No pude iniciar: {e}")
        return {"ok": False, "error": str(e)}
    return {"ok": True}


@app.post("/api/session/stop")
def session_stop():
    sess: Session | None = _state["session"]
    if not sess:
        return {"ok": True}
    sess.stop()
    return {"ok": True}


@app.get("/api/log")
def get_log(since: int = 0):
    with _log_lock:
        entries = [e for e in _log if e["i"] >= since]
    nxt = entries[-1]["i"] + 1 if entries else since
    return {"entries": entries, "next": nxt}
