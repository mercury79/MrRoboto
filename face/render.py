"""
Renderer.

Dibuja el vector facial en un framebuffer de 128x64 pixeles, 1 bit por pixel:
blanco o negro, sin grises, sin trampa. Exactamente lo que puede hacer la
SH1106.

La regla del simulador es esta: si algo no se ve bien aqui, tampoco se va a
ver bien en la OLED. Nada de antialiasing, nada de opacidad. Lo que veas en
la ventana es lo que va a salir en el hardware.

Cuando portemos a C++/U8g2, este archivo es el que se traduce. Las funciones
de dibujo tienen equivalente directo:
    draw_rect      -> u8g2.drawBox / drawFrame
    draw_disc      -> u8g2.drawDisc
    draw_line      -> u8g2.drawLine
"""

import math
import pygame

W, H = 128, 64
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def lerp(a, b, t):
    return a + (b - a) * t


def render(p, surface=None):
    """FaceParams -> pygame.Surface de 128x64, solo blanco y negro."""
    if surface is None:
        surface = pygame.Surface((W, H))
    surface.fill(BLACK)

    cx = W / 2 + p.face_x * 6
    cy = H / 2 + p.face_y * 4

    # --- geometria de los ojos ---
    spacing = lerp(24, 40, p.eye_spacing)
    eye_w = lerp(16, 30, p.eye_w)
    eye_h = lerp(10, 26, p.eye_h)
    eye_h *= (1.0 - p.squint * 0.45)
    radius = int(min(eye_w, eye_h) / 2 * p.eye_round)

    eye_cy = cy - 6
    lx = cx - spacing / 2
    rx = cx + spacing / 2

    tilt = p.tilt * 4

    _eye(surface, lx, eye_cy - tilt, eye_w, eye_h, radius,
         p.lid_top_l, p.lid_bot_l, p.gaze_x, p.gaze_y, p.pupil_r)
    _eye(surface, rx, eye_cy + tilt, eye_w, eye_h, radius,
         p.lid_top_r, p.lid_bot_r, p.gaze_x, p.gaze_y, p.pupil_r)

    # --- cejas ---
    brow_th = max(1, int(lerp(1, 4, p.brow_weight)))
    _brow(surface, lx, eye_cy - eye_h / 2 - 6 - tilt, eye_w,
          p.brow_l_y, p.brow_l_angle, brow_th, mirror=False)
    _brow(surface, rx, eye_cy - eye_h / 2 - 6 + tilt, eye_w,
          p.brow_r_y, p.brow_r_angle, brow_th, mirror=True)

    # --- boca ---
    _mouth(surface, cx, cy + 18, p)

    return surface


def _eye(surf, cx, cy, w, h, radius, lid_top, lid_bot, gaze_x, gaze_y, pupil_r):
    left = int(cx - w / 2)
    top = int(cy - h / 2)
    rect = pygame.Rect(left, top, int(w), int(h))

    if h < 2:
        pygame.draw.line(surf, WHITE, (left, int(cy)), (left + int(w), int(cy)))
        return

    pygame.draw.rect(surf, WHITE, rect, border_radius=radius)

    # pupila: hueco negro dentro del ojo blanco
    pr = lerp(2.0, 6.0, pupil_r)
    px = cx + gaze_x * (w / 2 - pr - 2)
    py = cy - gaze_y * (h / 2 - pr - 2)
    if h > pr * 2 + 2:
        pygame.draw.circle(surf, BLACK, (int(px), int(py)), int(pr))

    # parpados: rectangulos negros encima. Es literalmente como funciona
    # en la OLED (dibujas y borras), asi que el simulador no miente.
    if lid_top > 0.01:
        cover = int(h * lid_top) + 1
        pygame.draw.rect(surf, BLACK, pygame.Rect(left - 1, top - 1, int(w) + 2, cover))
    if lid_bot > 0.01:
        cover = int(h * lid_bot * 0.6) + 1
        pygame.draw.rect(surf, BLACK,
                         pygame.Rect(left - 1, top + int(h) - cover, int(w) + 2, cover + 1))


def _brow(surf, cx, cy, eye_w, height, angle, thickness, mirror):
    y = cy - height * 7
    half = eye_w / 2 + 1
    tilt = angle * 6
    if mirror:
        x1, y1 = cx + half, y + tilt * 0.3
        x2, y2 = cx - half, y - tilt
    else:
        x1, y1 = cx - half, y + tilt * 0.3
        x2, y2 = cx + half, y - tilt
    lo = thickness / 2 + 1
    y1 = max(lo, y1)
    y2 = max(lo, y2)
    pygame.draw.line(surf, WHITE, (int(x1), int(y1)), (int(x2), int(y2)), thickness)


def _mouth(surf, cx, cy, p):
    w = lerp(18, 52, p.mouth_w)
    th = max(1, int(lerp(1, 4, p.mouth_weight)))
    open_h = p.mouth_open * 20
    curve = p.mouth_curve * 11

    left = cx - w / 2
    right = cx + w / 2
    corner_l = -p.mouth_corner_l * 4
    corner_r = -p.mouth_corner_r * 4

    if open_h > 0:
        open_h = max(open_h, 4.0)

    if open_h < 2.5:
        # boca cerrada: una curva
        pts = _quad(left, cy + corner_l, cx, cy + curve, right, cy + corner_r)
        if len(pts) > 1:
            pygame.draw.lines(surf, WHITE, False, pts, th)
        return

    # boca abierta: dos curvas unidas, relleno blanco
    top = _quad(left, cy + corner_l, cx, cy + curve * 0.4, right, cy + corner_r)
    bot = _quad(right, cy + corner_r, cx, cy + open_h + curve * 0.3, left, cy + corner_l)
    poly = top + bot
    if len(poly) > 2:
        pygame.draw.polygon(surf, WHITE, poly)


def _quad(x0, y0, x1, y1, x2, y2, steps=14):
    """Bezier cuadratica muestreada. Barata y portable a C++."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u * u * x0 + 2 * u * t * x1 + t * t * x2
        y = u * u * y0 + 2 * u * t * y1 + t * t * y2
        pts.append((int(x), int(y)))
    return pts
