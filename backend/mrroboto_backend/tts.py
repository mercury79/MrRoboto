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
    """
    Reproduce PCM int16 mono SIN cortes y mueve la boca del robot con el RMS.

    Clave: el audio lo reproduce PortAudio (sd.play, con su propio buffer), y la
    boca se manda por HTTP en un HILO APARTE. Asi la latencia de la red al ESP32
    nunca frena el audio (ese era el motivo de que se oyera a tirones).
    """
    import threading
    import time

    import numpy as np
    import sounddevice as sd

    audio = np.frombuffer(pcm, dtype=np.int16)
    if audio.size == 0:
        return

    level = {"v": 0.0}
    done = threading.Event()

    def mouth_worker():
        # manda la boca a su propio ritmo (~11 Hz); el firmware suaviza
        while not done.is_set():
            if robot is not None:
                robot.mouth(level["v"])
            time.sleep(0.09)
        if robot is not None:
            robot.mouth(0.0)

    mt = threading.Thread(target=mouth_worker, daemon=True)
    mt.start()

    sd.play(audio, samplerate, device=output_device)   # no bloqueante, buffer interno = audio fluido
    try:
        win = max(1, int(samplerate * _BLOCK_S))
        n = audio.size
        t0 = time.time()
        idx = 0
        while idx < n:
            if stop_event is not None and stop_event.is_set():
                sd.stop()
                break
            chunk = audio[idx:idx + win]
            rms = float(np.sqrt(np.mean((chunk.astype(np.float32) / 32768.0) ** 2)))
            level["v"] = min(1.0, max(0.0, (rms * _MOUTH_GAIN) - _MOUTH_FLOOR))
            idx += win
            # avanza el envolvente en sincronia con el reloj del audio
            dt = (t0 + idx / samplerate) - time.time()
            if dt > 0:
                time.sleep(dt)
        sd.wait()
    finally:
        done.set()
        mt.join(timeout=0.5)


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
