"""
El oido: microfono -> VAD (detecta cuando hablas) -> Whisper (transcribe).

VAD (webrtcvad) trocea el audio en frases: arranca al detectar voz y cierra tras
un silencio. Cada frase se transcribe con faster-whisper (large-v3 = "Whisper 3"),
local y gratis. El modelo se descarga solo la primera vez.
"""

from __future__ import annotations


class WhisperSTT:
    def __init__(self, model: str = "large-v3", device: str = "auto",
                 compute_type: str = "auto", language: str = "es"):
        from faster_whisper import WhisperModel
        dev = None if device == "auto" else device
        ct = "default" if compute_type == "auto" else compute_type
        self.model = WhisperModel(model, device=(dev or "auto"), compute_type=ct)
        self.language = language or None

    def transcribe(self, pcm16: bytes, samplerate: int = 16000) -> str:
        import numpy as np
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size == 0:
            return ""
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,          # limpia silencios internos
            beam_size=1,              # rapido para conversacion
        )
        return " ".join(s.text.strip() for s in segments).strip()


class Listener:
    """Segmenta el microfono en frases con VAD. Half-duplex: se pausa mientras
    el robot habla, para no oirse a si mismo."""

    def __init__(self, vad_cfg: dict, input_device=None):
        self.aggr = int(vad_cfg.get("aggressiveness", 2))
        self.silence_ms = int(vad_cfg.get("silence_ms", 700))
        self.min_speech_ms = int(vad_cfg.get("min_speech_ms", 300))
        self.max_utterance_s = int(vad_cfg.get("max_utterance_s", 15))
        self.input_device = input_device

    def utterances(self, should_run, is_paused):
        """Generador: entrega el PCM (16 kHz int16) de cada frase detectada."""
        import sounddevice as sd
        import webrtcvad

        vad = webrtcvad.Vad(self.aggr)
        frame = 480              # 30 ms a 16 kHz (tamano valido para webrtcvad)
        frame_ms = 30

        with sd.InputStream(samplerate=16000, channels=1, dtype="int16",
                            blocksize=frame, device=self.input_device) as stream:
            voiced: list[bytes] = []
            triggered = False
            silence = 0
            while should_run():
                data, _ = stream.read(frame)
                if is_paused():
                    voiced.clear(); triggered = False; silence = 0
                    continue
                pcm = data[:, 0].tobytes()
                try:
                    is_speech = vad.is_speech(pcm, 16000)
                except Exception:  # noqa: BLE001 - frame invalido, ignora
                    continue

                if not triggered:
                    if is_speech:
                        triggered = True
                        voiced = [pcm]
                        silence = 0
                else:
                    voiced.append(pcm)
                    if is_speech:
                        silence = 0
                    else:
                        silence += frame_ms
                        if silence >= self.silence_ms:
                            if len(voiced) * frame_ms >= self.min_speech_ms:
                                yield b"".join(voiced)
                            triggered = False; voiced = []; silence = 0
                    if len(voiced) * frame_ms >= self.max_utterance_s * 1000:
                        yield b"".join(voiced)
                        triggered = False; voiced = []; silence = 0
