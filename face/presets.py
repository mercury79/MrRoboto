"""
Presets emocionales y cubo de Lovheim.

Dos capas:

1. PRESETS: cada emocion es un punto del vector facial.
2. CUBO DE LOVHEIM: el estado interno del agente son tres numeros continuos
   (serotonina, noradrenalina, dopamina) en 0..1. Las 8 esquinas del cubo son
   las 8 emociones basicas de Tomkins. Cualquier punto dentro del cubo se
   resuelve por interpolacion trilineal -> una cara valida.

   Esto es lo que hace que la cara sea un readout honesto del estado interno
   y no una animacion decorativa: no elegimos "cara feliz", movemos quimica
   y la cara cae donde tenga que caer.

Referencia: Lovheim, H. (2012). A new three-dimensional model for emotions
and monoamine neurotransmitters. Med Hypotheses 78(2):341-8.
"""

from .params import FaceParams, blend_many

# ----------------------------------------------------------------------
# Presets
# ----------------------------------------------------------------------

PRESETS = {
    # Cara de reposo. OJO: no es neutra, es CONTENTA.
    # Neutral se lee como "apagada". En calma no estamos apagados, estamos bien.
    "reposo": FaceParams(
        brow_l_y=0.05, brow_r_y=0.05,
        eye_w=0.55, eye_h=0.55, eye_round=0.65,
        lid_bot_l=0.10, lid_bot_r=0.10,
        pupil_r=0.5,
        mouth_curve=0.40, mouth_w=0.45, mouth_open=0.0, mouth_weight=0.5,
    ),

    "alegria": FaceParams(
        brow_l_y=0.35, brow_r_y=0.35,
        eye_w=0.6, eye_h=0.45, eye_round=0.8,
        lid_bot_l=0.45, lid_bot_r=0.45,   # el ojo que sonrie sube el parpado de abajo
        pupil_r=0.7,
        mouth_curve=0.9, mouth_w=0.7, mouth_open=0.35, mouth_weight=0.6,
        mouth_corner_l=0.5, mouth_corner_r=0.5,
    ),

    "interes": FaceParams(
        brow_l_y=0.5, brow_r_y=0.35,      # asimetrica: una ceja mas alta
        brow_l_angle=0.1,
        eye_w=0.65, eye_h=0.7, eye_round=0.7,
        pupil_r=0.75,
        gaze_y=0.1,
        mouth_curve=0.45, mouth_w=0.45, mouth_open=0.12,
        tilt=0.15,
    ),

    "sorpresa": FaceParams(
        brow_l_y=0.95, brow_r_y=0.95,
        eye_w=0.75, eye_h=0.95, eye_round=0.95,
        pupil_r=0.9,
        mouth_open=0.7, mouth_w=0.35, mouth_curve=0.0,
    ),

    "tristeza": FaceParams(
        brow_l_y=-0.1, brow_r_y=-0.1,
        brow_l_angle=0.85, brow_r_angle=0.85,   # puntas internas arriba: la firma de la tristeza
        eye_w=0.5, eye_h=0.45,
        lid_top_l=0.35, lid_top_r=0.35,
        pupil_r=0.4,
        gaze_y=-0.45,
        mouth_curve=-0.7, mouth_w=0.4, mouth_weight=0.45,
        mouth_corner_l=-0.5, mouth_corner_r=-0.5,
        face_y=-0.1,
    ),

    "enojo": FaceParams(
        brow_l_y=-0.8, brow_r_y=-0.8,
        brow_l_angle=-0.9, brow_r_angle=-0.9,
        brow_weight=0.9,
        eye_w=0.6, eye_h=0.4,
        squint=0.5,
        pupil_r=0.3,
        mouth_curve=-0.60, mouth_w=0.55, mouth_weight=0.7, mouth_open=0.0,
    ),

    "miedo": FaceParams(
        brow_l_y=0.8, brow_r_y=0.8,
        brow_l_angle=0.6, brow_r_angle=0.6,
        eye_w=0.7, eye_h=0.9, eye_round=0.9,
        pupil_r=0.95,
        gaze_x=-0.3,
        mouth_open=0.45, mouth_w=0.6, mouth_curve=-0.35,
    ),

    "desagrado": FaceParams(
        brow_l_y=-0.4, brow_r_y=-0.25,
        brow_l_angle=-0.4,
        eye_w=0.5, eye_h=0.35,
        squint=0.75,
        pupil_r=0.35,
        mouth_curve=-0.3, mouth_w=0.4, mouth_open=0.1,
        mouth_corner_l=0.4, mouth_corner_r=-0.5,   # asimetrica: media boca arriba
        tilt=-0.1,
    ),

    "verguenza": FaceParams(
        brow_l_y=-0.1, brow_r_y=-0.1,
        brow_l_angle=0.4, brow_r_angle=0.4,
        eye_w=0.45, eye_h=0.4,
        lid_top_l=0.5, lid_top_r=0.5,
        pupil_r=0.4,
        gaze_x=-0.5, gaze_y=-0.6,
        mouth_curve=-0.2, mouth_w=0.35,
        face_y=-0.15,
    ),

    "angustia": FaceParams(
        brow_l_y=0.2, brow_r_y=0.2,
        brow_l_angle=0.9, brow_r_angle=0.9,
        eye_w=0.55, eye_h=0.6,
        lid_top_l=0.2, lid_top_r=0.2,
        pupil_r=0.6,
        gaze_y=-0.2,
        mouth_curve=-0.8, mouth_w=0.5, mouth_open=0.25,
    ),

    "sueno": FaceParams(
        brow_l_y=-0.15, brow_r_y=-0.15,
        eye_w=0.5, eye_h=0.4,
        lid_top_l=0.8, lid_top_r=0.8,
        pupil_r=0.35,
        gaze_y=-0.2,
        mouth_curve=0.1, mouth_w=0.35,
        face_y=-0.08,
    ),
}


# ----------------------------------------------------------------------
# Cubo de Lovheim
# ----------------------------------------------------------------------
#
# Ejes: serotonina (S), noradrenalina (NA), dopamina (DA). Cada uno 0..1.
#
#   S  = confianza, fuerza interior, satisfaccion
#   NA = activacion, vigilancia, atencion
#   DA = recompensa, motivacion, refuerzo
#
# Las 8 esquinas, segun el modelo:
#
#   S  NA  DA   emocion
#   0   0   0   verguenza / humillacion
#   0   1   0   angustia / afliccion
#   0   0   1   desagrado / desprecio
#   0   1   1   enojo / rabia
#   1   0   0   miedo / terror
#   1   1   0   sorpresa
#   1   0   1   alegria / gozo
#   1   1   1   interes / entusiasmo
#
# Nota: en este modelo el miedo NO cae en noradrenalina alta. Es
# contraintuitivo pero es lo que dice Lovheim: el eje de la pelea-o-huida
# no se mapea como uno esperaria.

CUBE_CORNERS = {
    (0, 0, 0): "verguenza",
    (0, 1, 0): "angustia",
    (0, 0, 1): "desagrado",
    (0, 1, 1): "enojo",
    (1, 0, 0): "miedo",
    (1, 1, 0): "sorpresa",
    (1, 0, 1): "alegria",
    (1, 1, 1): "interes",
}


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def from_lovheim(serotonina: float, noradrenalina: float, dopamina: float) -> FaceParams:
    """
    Estado quimico continuo -> cara.

    Interpolacion trilineal entre las 8 esquinas del cubo. El peso de cada
    esquina es el producto de que tan cerca esta el punto en cada eje.
    """
    s = clamp01(serotonina)
    n = clamp01(noradrenalina)
    d = clamp01(dopamina)

    pairs = []
    for (cs, cn, cd), name in CUBE_CORNERS.items():
        w = (s if cs else 1 - s) * (n if cn else 1 - n) * (d if cd else 1 - d)
        if w > 0.001:
            pairs.append((PRESETS[name], w))

    if not pairs:
        return PRESETS["reposo"].copy()
    return blend_many(pairs)


def dominant_emotion(serotonina: float, noradrenalina: float, dopamina: float) -> str:
    """Etiqueta de la esquina mas cercana. Solo para debug y logs."""
    s, n, d = clamp01(serotonina), clamp01(noradrenalina), clamp01(dopamina)
    best, best_w = "reposo", -1.0
    for (cs, cn, cd), name in CUBE_CORNERS.items():
        w = (s if cs else 1 - s) * (n if cn else 1 - n) * (d if cd else 1 - d)
        if w > best_w:
            best, best_w = name, w
    return best


# Etiquetas de voz -> empujon quimico.
# El agente escribe [laughs] en su texto: ElevenLabs lo convierte en risa y
# nosotros lo convertimos en cara. Un solo token, dos efectos, cero
# clasificador externo.
VOICE_TAGS = {
    "[laughs]":     (0.15, -0.05, 0.25),
    "[chuckles]":   (0.10, -0.05, 0.15),
    "[sighs]":      (-0.15, -0.10, -0.20),
    "[gasps]":      (0.05, 0.35, 0.05),
    "[whispers]":   (0.0, -0.15, -0.05),
    "[excited]":    (0.10, 0.25, 0.30),
    "[sad]":        (-0.25, 0.05, -0.25),
    "[angry]":      (-0.35, 0.30, 0.20),
    "[curious]":    (0.10, 0.20, 0.15),
}
