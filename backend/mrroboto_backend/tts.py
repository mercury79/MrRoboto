"""
Voz (texto -> audio) + sincronia de boca.

Dos motores:
  - elevenlabs : natural, de pago. Pide PCM 16 kHz para poder mover la boca.
  - pyttsx3    : gratis, offline (voces SAPI de Windows). Menos natural pero cero costo.

Mientras suena el audio, calculamos el envolvente RMS por bloques y lo mandamos
a GET /face?mouth= del robot, para que la boca siga la voz. El firmware tiene
watchdog: si dejamos de mandar, la boca cierra sola a los 400 ms.
"""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

_MOUTH_GAIN = 3.2      # la voz tiene RMS bajo; amplificamos para abrir bien la boca
_MOUTH_FLOOR = 0.06    # por debajo de esto, boca cerrada (ruido)
_BLOCK_S = 0.06        # 60 ms por bloque (~16 Hz de refresco de boca)


# ----------------------------------------------------------------------
# Verificacion de key
# ----------------------------------------------------------------------

def verify_key(api_key: str) -> tuple[bool, str]:
    if not api_key:
        return False, "No hay API key."
    try:
        from elevenlabs.client import ElevenLabs
    except ImportError:
        return False, "Falta el paquete 'elevenlabs' (instala dependencias)."
    try:
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all()
        n = len(getattr(voices, "voices", []) or [])
        return True, f"Key de ElevenLabs valida ({n} voces disponibles)."
    except Exception as e:  # noqa: BLE001
        return False, f"Error verificando ElevenLabs: {e}"


def list_voices(api_key: str) -> list[dict]:
    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all()
        return [{"id": v.voice_id, "name": v.name} for v in voices.voices]
    except Exception:  # noqa: BLE001
        return []


# ----------------------------------------------------------------------
# Reproduccion con sincronia de boca
# ----------------------------------------------------------------------

def _play_pcm(pcm: bytes, samplerate: int, robot, stop_event, output_device=None) -> None:
    """Reproduce PCM int16 mono y mueve la boca del robot con el RMS."""
    import numpy as np
    import sounddevice as sd

    audio = np.frombuffer(pcm, dtype=np.int16)
    if audio.size == 0:
        return
    block = max(1, int(samplerate * _BLOCK_S))

    with sd.OutputStream(samplerate=samplerate, channels=1, dtype="int16",
                         device=output_device) as stream:
        for start in range(0, audio.size, block):
            if stop_event is not None and stop_event.is_set():
                break
            chunk = audio[start:start + block]
            # RMS normalizado 0..1
            rms = float(np.sqrt(np.mean((chunk.astype(np.float32) / 32768.0) ** 2)))
            level = max(0.0, (rms * _MOUTH_GAIN) - _MOUTH_FLOOR)
            level = min(1.0, level)
            if robot is not None:
                robot.mouth(level)               # se manda ANTES de oirse: compensa el viaje al ESP32
            stream.write(chunk)
    if robot is not None:
        robot.mouth(0.0)


def _speak_elevenlabs(text: str, cfg: dict, api_key: str, robot, stop_event,
                      output_device=None) -> None:
    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=api_key)

    voice_id = (cfg.get("voice_id") or "").strip()
    if not voice_id:
        voices = client.voices.get_all().voices
        if not voices:
            raise RuntimeError("La cuenta de ElevenLabs no tiene voces.")
        voice_id = voices[0].voice_id

    # PCM crudo a 16 kHz: nos deja calcular RMS y reproducir sin decodificar mp3.
    audio_iter = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=cfg.get("model", "eleven_flash_v2_5"),
        text=text,
        output_format="pcm_16000",
    )
    pcm = b"".join(audio_iter)
    _play_pcm(pcm, 16000, robot, stop_event, output_device)


def _speak_free(text: str, cfg: dict, robot, stop_event, output_device=None) -> None:
    """pyttsx3 -> WAV temporal -> reproducir con sincronia de boca."""
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty("rate", int(cfg.get("free_rate", 175)))
    want = (cfg.get("free_voice") or "").strip().lower()
    if want:
        for v in engine.getProperty("voices"):
            if want in (v.name or "").lower():
                engine.setProperty("voice", v.id)
                break

    tmp = Path(tempfile.gettempdir()) / "mrroboto_tts.wav"
    engine.save_to_file(text, str(tmp))
    engine.runAndWait()

    with wave.open(str(tmp), "rb") as wf:
        sr = wf.getframerate()
        n_ch = wf.getnchannels()
        pcm = wf.readframes(wf.getnframes())

    if n_ch == 2:  # a mono si hiciera falta
        import numpy as np
        a = np.frombuffer(pcm, dtype=np.int16).reshape(-1, 2).mean(axis=1).astype(np.int16)
        pcm = a.tobytes()
    _play_pcm(pcm, sr, robot, stop_event, output_device)


def speak(text: str, cfg: dict, secrets: dict, robot, stop_event=None,
          output_device=None) -> None:
    """Punto de entrada. Elige motor segun cfg['engine']."""
    text = (text or "").strip()
    if not text:
        return
    engine = cfg.get("engine", "elevenlabs")
    if engine == "elevenlabs":
        key = secrets.get("elevenlabs_api_key", "")
        if not key:
            raise RuntimeError("Falta la API key de ElevenLabs (o cambia a la voz gratis).")
        _speak_elevenlabs(text, cfg, key, robot, stop_event, output_device)
    else:
        _speak_free(text, cfg, robot, stop_event, output_device)
