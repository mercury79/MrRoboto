"""
Motor facial: estado emocional + capas de vida.

Las "capas de vida" son lo que separa una cara viva de un dibujo: parpadeo
estocastico, sacadas y respiracion, corriendo a 30 Hz aunque no pase
absolutamente nada. Aunque no pase nada, algo pasa.

IMPORTANTE para el port al ESP32: estas capas van EN EL FIRMWARE, no en el
backend. Si dependen de la red, un lag de 200 ms congela la cara a media
palabra y se rompe la ilusion. El backend manda intencion; el firmware la
mantiene viva.
"""

import math
import random
import time

from .params import FaceParams
from .presets import from_lovheim, dominant_emotion, VOICE_TAGS, clamp01


class FaceEngine:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)

        # Estado quimico. Arranca en la esquina de alegria pero moderado:
        # la cara de reposo es contenta, no neutra.
        self.serotonina = 0.70
        self.noradrenalina = 0.30
        self.dopamina = 0.60

        # Homeostasis: hacia donde regresa solo con el tiempo.
        self.baseline = (0.70, 0.30, 0.60)
        self.decay_rate = 0.12      # por segundo

        # Suavizado de la cara hacia el objetivo
        self.current = from_lovheim(*self._chem())
        self.smoothing = 7.0        # mayor = mas rapido

        # --- parpadeo ---
        self._blink_t = 0.0
        self._blink_dur = 0.0
        self._next_blink = self._schedule_blink()

        # --- sacadas ---
        self._gaze_x = 0.0
        self._gaze_y = 0.0
        self._gaze_tx = 0.0
        self._gaze_ty = 0.0
        self._next_saccade = self.rng.uniform(0.4, 1.6)

        # --- respiracion ---
        self._breath_phase = self.rng.uniform(0, math.tau)
        self.breath_hz = 0.22

        # --- boca por voz ---
        self._mouth = 0.0
        self._mouth_target = 0.0
        self._last_mouth_update = 0.0
        self.mouth_watchdog = 0.400   # s: si muere el stream, cierra sola

        self._t = 0.0

    # ------------------------------------------------------------------
    # Estado emocional
    # ------------------------------------------------------------------

    def _chem(self):
        return (self.serotonina, self.noradrenalina, self.dopamina)

    def set_chem(self, s=None, n=None, d=None):
        if s is not None:
            self.serotonina = clamp01(s)
        if n is not None:
            self.noradrenalina = clamp01(n)
        if d is not None:
            self.dopamina = clamp01(d)

    def nudge(self, ds=0.0, dn=0.0, dd=0.0):
        """Empujon relativo al estado actual."""
        self.serotonina = clamp01(self.serotonina + ds)
        self.noradrenalina = clamp01(self.noradrenalina + dn)
        self.dopamina = clamp01(self.dopamina + dd)

    def apply_voice_tag(self, tag: str):
        """[laughs], [sighs], etc. Mueve la quimica, no fuerza una cara."""
        delta = VOICE_TAGS.get(tag.lower().strip())
        if delta:
            self.nudge(*delta)
            return True
        return False

    def apply_text(self, text: str):
        """Extrae todas las etiquetas de un texto del agente y las aplica."""
        found = []
        low = text.lower()
        for tag in VOICE_TAGS:
            if tag in low:
                self.apply_voice_tag(tag)
                found.append(tag)
        return found

    @property
    def emotion_label(self) -> str:
        return dominant_emotion(*self._chem())

    # ------------------------------------------------------------------
    # Boca
    # ------------------------------------------------------------------

    def set_mouth(self, value: float):
        """
        Llamado desde el backend con el envolvente RMS del audio (0..1).
        En el robot real esto entra como GET /face?mouth=0.63
        """
        self._mouth_target = clamp01(value)
        self._last_mouth_update = self._t

    # ------------------------------------------------------------------
    # Capas de vida
    # ------------------------------------------------------------------

    def _schedule_blink(self) -> float:
        # Los parpadeos humanos no son periodicos: se agrupan.
        # Distribucion sesgada a intervalos cortos con cola larga.
        base = self.rng.expovariate(1 / 3.2)
        return max(0.8, min(9.0, base))

    def _update_blink(self, dt):
        self._next_blink -= dt
        if self._blink_dur > 0:
            self._blink_t += dt
            if self._blink_t >= self._blink_dur:
                self._blink_dur = 0.0
                self._blink_t = 0.0
        elif self._next_blink <= 0:
            self._blink_dur = self.rng.uniform(0.09, 0.16)
            self._blink_t = 0.0
            self._next_blink = self._schedule_blink()
            # a veces doble parpadeo
            if self.rng.random() < 0.18:
                self._next_blink = self.rng.uniform(0.25, 0.5)

    def _blink_amount(self) -> float:
        """0 = ojo abierto, 1 = cerrado. Cierre rapido, apertura mas lenta."""
        if self._blink_dur <= 0:
            return 0.0
        p = self._blink_t / self._blink_dur
        if p < 0.4:
            return (p / 0.4) ** 0.7
        return (1 - (p - 0.4) / 0.6) ** 1.6

    def _update_saccades(self, dt):
        self._next_saccade -= dt
        if self._next_saccade <= 0:
            # micro-dardos casi siempre, salto grande de vez en cuando
            if self.rng.random() < 0.15:
                self._gaze_tx = self.rng.uniform(-0.8, 0.8)
                self._gaze_ty = self.rng.uniform(-0.5, 0.5)
                self._next_saccade = self.rng.uniform(1.0, 3.0)
            else:
                self._gaze_tx = clamp_sym(self._gaze_tx + self.rng.gauss(0, 0.12))
                self._gaze_ty = clamp_sym(self._gaze_ty + self.rng.gauss(0, 0.07))
                self._next_saccade = self.rng.uniform(0.25, 1.1)

        # las sacadas son casi instantaneas: ~40 ms
        k = min(1.0, dt / 0.04)
        self._gaze_x += (self._gaze_tx - self._gaze_x) * k
        self._gaze_y += (self._gaze_ty - self._gaze_y) * k

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> FaceParams:
        self._t += dt

        # homeostasis
        bs, bn, bd = self.baseline
        k = min(1.0, self.decay_rate * dt)
        self.serotonina += (bs - self.serotonina) * k
        self.noradrenalina += (bn - self.noradrenalina) * k
        self.dopamina += (bd - self.dopamina) * k

        # cara objetivo segun quimica, suavizada
        target = from_lovheim(*self._chem())
        blend = min(1.0, self.smoothing * dt)
        self.current = self.current.blend(target, blend)

        out = self.current.copy()

        # --- capa: respiracion ---
        self._breath_phase += dt * self.breath_hz * math.tau
        breath = math.sin(self._breath_phase)
        out.face_y += breath * 0.06
        out.eye_h += breath * 0.015

        # --- capa: sacadas ---
        self._update_saccades(dt)
        out.gaze_x = clamp_sym(out.gaze_x + self._gaze_x * 0.35)
        out.gaze_y = clamp_sym(out.gaze_y + self._gaze_y * 0.25)

        # --- capa: parpadeo ---
        self._update_blink(dt)
        b = self._blink_amount()
        if b > 0:
            out.lid_top_l = max(out.lid_top_l, b)
            out.lid_top_r = max(out.lid_top_r, b)

        # --- capa: boca por voz ---
        if self._t - self._last_mouth_update > self.mouth_watchdog:
            self._mouth_target = 0.0
        km = min(1.0, dt / 0.05)
        self._mouth += (self._mouth_target - self._mouth) * km
        if self._mouth > 0.01:
            out.mouth_open = max(out.mouth_open, self._mouth * 0.85)

        return out


def clamp_sym(x: float) -> float:
    return max(-1.0, min(1.0, x))
