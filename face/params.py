"""
Vector de parametros faciales.

La cara NO son dibujos por emocion. Es un vector continuo de ~25 numeros.
Cada emocion es solo un preset de este vector, y cualquier punto intermedio
es una cara valida. Esto es lo que permite mezclar estados en vez de
saltar entre sprites.

Este archivo es la unica fuente de verdad del formato. Cuando portemos al
ESP32, el struct de C++ debe tener EXACTAMENTE estos campos en este orden.
"""

from dataclasses import dataclass, fields

# Rangos: casi todo va de -1..1 o de 0..1. Ver comentario de cada campo.


@dataclass
class FaceParams:
    # --- Cejas (5) ---
    brow_l_y: float = 0.0        # -1 hundida (enojo) .. +1 levantada (sorpresa)
    brow_r_y: float = 0.0
    brow_l_angle: float = 0.0    # -1 punta interna abajo .. +1 punta interna arriba (tristeza)
    brow_r_angle: float = 0.0
    brow_weight: float = 0.5     # 0 fina .. 1 gruesa

    # --- Parpados (4) ---
    lid_top_l: float = 0.0       # 0 abierto .. 1 cerrado del todo
    lid_top_r: float = 0.0
    lid_bot_l: float = 0.0       # parpado inferior: sube al sonreir de verdad
    lid_bot_r: float = 0.0

    # --- Ojos (4) ---
    eye_w: float = 0.5           # 0 angosto .. 1 ancho
    eye_h: float = 0.5           # 0 aplastado .. 1 alto
    eye_round: float = 0.6       # 0 rectangular .. 1 circular
    eye_spacing: float = 0.5     # separacion entre ojos

    # --- Pupilas / mirada (4) ---
    pupil_r: float = 0.5         # 0 contraida .. 1 dilatada
    gaze_x: float = 0.0          # -1 izquierda .. +1 derecha
    gaze_y: float = 0.0          # -1 abajo .. +1 arriba
    squint: float = 0.0          # 0 nada .. 1 entrecerrado (desconfianza)

    # --- Boca (6) ---
    mouth_open: float = 0.0      # 0 cerrada .. 1 abierta al maximo
    mouth_w: float = 0.5         # ancho
    mouth_curve: float = 0.0     # -1 hacia abajo .. +1 sonrisa
    mouth_corner_l: float = 0.0  # asimetria: -1 comisura abajo .. +1 arriba
    mouth_corner_r: float = 0.0
    mouth_weight: float = 0.5    # grosor del trazo

    # --- Global (3) ---
    face_x: float = 0.0          # desplazamiento lateral (sway)
    face_y: float = 0.0          # desplazamiento vertical (respiracion)
    tilt: float = 0.0            # -1 .. +1 inclinacion

    # ---------------------------------------------------------------

    def copy(self) -> "FaceParams":
        return FaceParams(**{f.name: getattr(self, f.name) for f in fields(self)})

    def blend(self, other: "FaceParams", t: float) -> "FaceParams":
        """Interpolacion lineal entre dos caras. t=0 -> self, t=1 -> other."""
        t = max(0.0, min(1.0, t))
        out = FaceParams()
        for f in fields(self):
            a = getattr(self, f.name)
            b = getattr(other, f.name)
            setattr(out, f.name, a + (b - a) * t)
        return out

    def as_list(self):
        """Orden estable. Es el mismo orden que usara el firmware."""
        return [getattr(self, f.name) for f in fields(self)]

    @staticmethod
    def field_names():
        return [f.name for f in fields(FaceParams)]


def blend_many(pairs) -> FaceParams:
    """
    Mezcla ponderada de varias caras.
    pairs = [(FaceParams, peso), ...]. Los pesos se normalizan.
    """
    total = sum(w for _, w in pairs)
    if total <= 0:
        return FaceParams()
    out = FaceParams()
    for f in fields(FaceParams):
        acc = sum(getattr(p, f.name) * w for p, w in pairs)
        setattr(out, f.name, acc / total)
    return out
