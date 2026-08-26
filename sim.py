"""
Simulador del motor facial.

Corre la cara completa en la PC, sin hardware. Lo que ves en la ventana es
pixel por pixel lo que va a salir en la SH1106.

    python sim.py

Teclas:
    1..9, 0     presets emocionales
    R           volver a reposo
    Flechas     mover el estado quimico (S / NA)
    Q / A       subir / bajar dopamina
    M           micro encendido/apagado (la boca sigue tu voz)
    D           mostrar/ocultar panel de debug
    ESC         salir

El micro usa el envolvente RMS del audio, igual que va a hacerlo el backend
cuando hable ElevenLabs. Si no tienes sounddevice instalado, todo lo demas
sigue funcionando.
"""

import sys
import time
import math

import pygame

from face.engine import FaceEngine
from face.render import render, W, H
from face.presets import PRESETS

SCALE = 6
FPS = 60

# --- audio opcional ---
try:
    import sounddevice as sd
    import numpy as np
    HAVE_AUDIO = True
except Exception:
    HAVE_AUDIO = False


class MicMouth:
    """
    Envolvente RMS del microfono -> apertura de boca.

    Ventanas de ~150 ms empujadas a ~7 Hz, que es la cadencia silabica del
    habla. Mas rapido que eso y la boca tiembla; mas lento y se ve como
    doblaje mal sincronizado.

    En el robot real habra que ADELANTAR ~120 ms para compensar el viaje
    hasta la placa. Aqui no hace falta: el render es local.
    """

    WINDOW = 0.150
    RATE = 16000

    def __init__(self):
        self.level = 0.0
        self.floor = 0.004
        self.ceil = 0.06
        self.stream = None

    def start(self):
        if not HAVE_AUDIO:
            return False
        block = int(self.RATE * self.WINDOW)
        try:
            self.stream = sd.InputStream(
                samplerate=self.RATE, channels=1, blocksize=block,
                callback=self._cb)
            self.stream.start()
            return True
        except Exception as e:
            print(f"[mic] no se pudo abrir: {e}")
            return False

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _cb(self, indata, frames, t, status):
        rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        # normaliza contra piso y techo adaptativos
        self.floor = min(self.floor * 1.0005, max(0.0005, rms)) \
            if rms < self.floor else self.floor
        self.ceil = max(self.ceil * 0.9995, rms) if rms > self.ceil else self.ceil
        span = max(1e-6, self.ceil - self.floor)
        self.level = max(0.0, min(1.0, (rms - self.floor) / span))


PRESET_KEYS = [
    (pygame.K_1, "alegria"),
    (pygame.K_2, "interes"),
    (pygame.K_3, "sorpresa"),
    (pygame.K_4, "tristeza"),
    (pygame.K_5, "enojo"),
    (pygame.K_6, "miedo"),
    (pygame.K_7, "desagrado"),
    (pygame.K_8, "verguenza"),
    (pygame.K_9, "angustia"),
    (pygame.K_0, "sueno"),
]

# preset -> esquina quimica, para que las teclas muevan la quimica y no
# pinten la cara a mano. La cara siempre sale del estado interno.
PRESET_CHEM = {
    "verguenza": (0.05, 0.05, 0.05),
    "angustia":  (0.05, 0.95, 0.05),
    "desagrado": (0.05, 0.05, 0.95),
    "enojo":     (0.05, 0.95, 0.95),
    "miedo":     (0.95, 0.05, 0.05),
    "sorpresa":  (0.95, 0.95, 0.05),
    "alegria":   (0.95, 0.05, 0.95),
    "interes":   (0.95, 0.95, 0.95),
    "sueno":     (0.55, 0.02, 0.15),
}


def main():
    pygame.init()
    pygame.display.set_caption("MrRoboto - motor facial (SH1106 128x64)")

    panel_h = 96
    screen = pygame.display.set_mode((W * SCALE, H * SCALE + panel_h))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,monospace", 14)

    engine = FaceEngine()
    fb = pygame.Surface((W, H))

    mic = MicMouth()
    mic_on = False
    show_debug = True

    last = time.perf_counter()
    running = True

    while running:
        now = time.perf_counter()
        dt = min(0.1, now - last)
        last = now

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    engine.set_chem(*engine.baseline)
                elif ev.key == pygame.K_d:
                    show_debug = not show_debug
                elif ev.key == pygame.K_m:
                    if mic_on:
                        mic.stop()
                        mic_on = False
                    else:
                        mic_on = mic.start()
                        if not mic_on:
                            print("[mic] instala sounddevice: pip install sounddevice numpy")
                else:
                    for key, name in PRESET_KEYS:
                        if ev.key == key and name in PRESET_CHEM:
                            engine.set_chem(*PRESET_CHEM[name])

        keys = pygame.key.get_pressed()
        step = 0.6 * dt
        if keys[pygame.K_LEFT]:
            engine.nudge(ds=-step)
        if keys[pygame.K_RIGHT]:
            engine.nudge(ds=step)
        if keys[pygame.K_UP]:
            engine.nudge(dn=step)
        if keys[pygame.K_DOWN]:
            engine.nudge(dn=-step)
        if keys[pygame.K_q]:
            engine.nudge(dd=step)
        if keys[pygame.K_a]:
            engine.nudge(dd=-step)

        if mic_on:
            engine.set_mouth(mic.level)

        params = engine.update(dt)
        render(params, fb)

        screen.fill((18, 18, 20))
        # nearest-neighbor a proposito: queremos ver los pixeles
        scaled = pygame.transform.scale(fb, (W * SCALE, H * SCALE))
        screen.blit(scaled, (0, 0))
        pygame.draw.rect(screen, (60, 60, 70),
                         pygame.Rect(0, 0, W * SCALE, H * SCALE), 1)

        if show_debug:
            y = H * SCALE + 8
            s, n, d = engine.serotonina, engine.noradrenalina, engine.dopamina
            lines = [
                f"emocion: {engine.emotion_label:<12}  boca: {params.mouth_open:.2f}"
                f"   mic: {'ON' if mic_on else 'off'}",
                f"serotonina    {_bar(s)} {s:.2f}   <- ->",
                f"noradrenalina {_bar(n)} {n:.2f}   arriba/abajo",
                f"dopamina      {_bar(d)} {d:.2f}   Q/A",
            ]
            for ln in lines:
                screen.blit(font.render(ln, True, (170, 180, 190)), (10, y))
                y += 20

        pygame.display.flip()
        clock.tick(FPS)

    mic.stop()
    pygame.quit()


def _bar(v, width=18):
    n = int(v * width)
    return "[" + "#" * n + "-" * (width - n) + "]"


if __name__ == "__main__":
    main()
