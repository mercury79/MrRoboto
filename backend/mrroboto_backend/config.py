"""
Preferencias persistentes + API keys.

Dos archivos en backend/config/ (ambos gitignored, nunca suben al repo):
  - settings.json : todas las opciones que tocas en el panel.
  - secrets.json  : las API keys en claro, SOLO en tu maquina.

Regla: lo sensible se queda local. El repo trae los DEFAULTS de abajo; tu
configuracion real vive en config/ y no se comparte.
"""

from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path

# backend/  (dos niveles arriba de este archivo: mrroboto_backend/config.py)
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
FACES_DIR = CONFIG_DIR / "faces"
MODELS_DIR = BASE_DIR / "models"
WEB_DIR = BASE_DIR / "web"

SETTINGS_PATH = CONFIG_DIR / "settings.json"
SECRETS_PATH = CONFIG_DIR / "secrets.json"

_lock = threading.Lock()

# ----------------------------------------------------------------------
# Defaults. El panel los edita; se guardan en settings.json.
# ----------------------------------------------------------------------

DEFAULT_PERSONA = (
    "Eres MrRoboto, una cabeza robotica de escritorio con personalidad calida, "
    "curiosa y con humor seco. Hablas en espanol, de forma natural y BREVE: "
    "esto es una conversacion por voz, no un ensayo. Responde en 1-3 frases "
    "salvo que te pidan mas. Puedes usar etiquetas de emocion entre corchetes "
    "que se convierten en sonido y en tu cara: [laughs], [chuckles], [sighs], "
    "[gasps], [whispers], [excited], [curious]. Usalas con moderacion, solo "
    "cuando de verdad aporten. No describas acciones fisicas ni uses emojis."
)

DEFAULTS = {
    "robot": {
        "ip": "192.168.0.46",       # IP del ESP32 (verbos HTTP del paso 4)
        "enabled": True,            # si False, el backend no toca el robot
        "timeout_s": 3.0,
    },
    "stt": {
        "engine": "faster-whisper",  # unico por ahora; gratis y local
        "model": "large-v3",         # "Whisper 3". Alternativas: large-v3-turbo, medium, small, base, tiny
        "language": "es",            # "" = autodetectar
        "device": "auto",            # auto | cpu | cuda
        "compute_type": "auto",      # auto | int8 | float16 | float32
    },
    "vad": {
        "aggressiveness": 2,         # 0..3 (mas alto = corta antes el ruido)
        "silence_ms": 700,           # silencio que cierra una frase
        "min_speech_ms": 300,        # minimo para considerar que hablaste
        "max_utterance_s": 15,       # tope duro por frase
    },
    "llm": {
        "provider": "anthropic",
        # Default fluido y economico para voz en tiempo real. Opciones en el panel:
        #   claude-haiku-4-5 (rapido/barato), claude-sonnet-5 (equilibrado),
        #   claude-opus-5 (premium).
        "model": "claude-haiku-4-5",
        "max_tokens": 400,           # respuestas cortas para voz
        "persona": DEFAULT_PERSONA,
        "history_turns": 12,         # cuantos turnos recordar
    },
    "tts": {
        "engine": "elevenlabs",      # elevenlabs (pago) | pyttsx3 (gratis, offline)
        "voice_id": "",              # id de voz de ElevenLabs (vacio = una por defecto)
        "model": "eleven_flash_v2_5",  # baja latencia y barato. Calidad: eleven_multilingual_v2
        "free_rate": 175,            # velocidad de la voz gratis (pyttsx3)
        "free_voice": "",            # nombre de voz SAPI (vacio = la del sistema)
    },
    "vision": {
        "enabled": True,
        "camera_index": 0,           # C920 suele ser 0
        "recognize": True,           # reconocerte y saludarte por tu nombre
        "greet_cooldown_s": 30,      # no saludar en bucle
        "confidence": 65,            # umbral LBPH (menor = mas estricto)
    },
    "audio": {
        "input_device": None,        # None = microfono por defecto (el de la C920)
        "output_device": None,       # None = bocina por defecto
    },
    "session": {
        "speak_greeting": True,      # ademas de la cara, decir "hola" al reconocerte
    },
}

SECRET_DEFAULTS = {
    "anthropic_api_key": "",
    "elevenlabs_api_key": "",
}


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------

def _deep_merge(base: dict, over: dict) -> dict:
    """Mezcla 'over' sobre 'base' recursivamente (over gana)."""
    out = deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    """Defaults + lo guardado. Siempre devuelve el arbol completo."""
    ensure_dirs()
    saved = {}
    if SETTINGS_PATH.exists():
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            saved = {}
    return _deep_merge(DEFAULTS, saved)


def save_settings(settings: dict) -> dict:
    """Guarda solo lo que difiere/entrega el panel; devuelve el arbol completo."""
    ensure_dirs()
    with _lock:
        merged = _deep_merge(DEFAULTS, settings or {})
        SETTINGS_PATH.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return merged


def load_secrets() -> dict:
    ensure_dirs()
    if SECRETS_PATH.exists():
        try:
            data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
            return _deep_merge(SECRET_DEFAULTS, data)
        except (json.JSONDecodeError, OSError):
            pass
    return deepcopy(SECRET_DEFAULTS)


def save_secrets(secrets: dict) -> None:
    """Guarda las keys en claro, solo local. Intenta permisos restringidos."""
    ensure_dirs()
    with _lock:
        current = load_secrets()
        # Solo sobreescribe las que vengan no-vacias (permite guardar una sola).
        for k, v in (secrets or {}).items():
            if k in SECRET_DEFAULTS and v is not None:
                current[k] = v.strip() if isinstance(v, str) else v
        SECRETS_PATH.write_text(
            json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    try:
        os.chmod(SECRETS_PATH, 0o600)  # best-effort en Windows
    except OSError:
        pass


def secret_status() -> dict:
    """Que keys estan puestas, SIN revelar su valor (para el panel)."""
    s = load_secrets()
    out = {}
    for k in SECRET_DEFAULTS:
        val = s.get(k, "") or ""
        out[k] = {
            "set": bool(val),
            "hint": (val[:3] + "..." + val[-4:]) if len(val) > 8 else ("***" if val else ""),
        }
    return out
