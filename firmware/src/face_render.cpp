// Renderer facial para U8g2. Traduccion 1:1 de face/render.py.
// Todo en 128x64, 1 bit. Sin antialiasing, sin grises: lo que se ve aqui es
// lo que sale en la SH1106.

#include "face_render.h"
#include <math.h>

static const int W = 128;
static const int H = 64;

static inline float lerp(float a, float b, float t) { return a + (b - a) * t; }

// --- primitivas que U8g2 no trae directas -------------------------------

// Caja rellena con recorte a pantalla. En negro (setDrawColor 0) sirve para
// perforar (parpados); coords pueden venir negativas, por eso el clip.
static void fillBox(U8G2& u, int x, int y, int w, int h) {
  if (w <= 0 || h <= 0) return;
  if (x < 0) { w += x; x = 0; }
  if (y < 0) { h += y; y = 0; }
  if (x >= W || y >= H) return;
  if (x + w > W) w = W - x;
  if (y + h > H) h = H - y;
  if (w <= 0 || h <= 0) return;
  u.drawBox(x, y, w, h);
}

// Caja rellena con esquinas redondeadas. Equivale a pygame border_radius.
// U8g2 drawRBox exige un radio que quepa; lo clampeamos y caemos a caja recta
// si el radio es demasiado chico.
static void fillRoundBox(U8G2& u, int x, int y, int w, int h, int r) {
  if (w <= 0 || h <= 0) return;
  int maxr = ((w < h ? w : h) - 1) / 2;
  if (r > maxr) r = maxr;
  if (r < 1) { u.drawBox(x, y, w, h); return; }
  u.drawRBox(x, y, w, h, r);
}

// Linea con grosor: apilamos "th" lineas desplazadas en vertical. Basta para
// cejas y boca, que son casi horizontales (== pygame line width).
static void thickLine(U8G2& u, int x0, int y0, int x1, int y1, int th) {
  if (th < 1) th = 1;
  int base = -(th / 2);
  for (int i = 0; i < th; i++) u.drawLine(x0, y0 + base + i, x1, y1 + base + i);
}

// Poligono relleno via abanico de triangulos desde el primer vertice. La
// boca abierta es convexa (una lente), asi que el abanico la llena limpio.
static void fillPolygon(U8G2& u, const int* xs, const int* ys, int n) {
  for (int i = 1; i < n - 1; i++)
    u.drawTriangle(xs[0], ys[0], xs[i], ys[i], xs[i + 1], ys[i + 1]);
}

// Bezier cuadratica muestreada (== _quad de render.py). Escribe steps+1
// puntos en xs/ys y devuelve la cantidad.
static int quad(float x0, float y0, float x1, float y1, float x2, float y2,
                int* xs, int* ys, int steps = 14) {
  for (int i = 0; i <= steps; i++) {
    float t = (float)i / steps;
    float u = 1.0f - t;
    xs[i] = (int)(u * u * x0 + 2 * u * t * x1 + t * t * x2);
    ys[i] = (int)(u * u * y0 + 2 * u * t * y1 + t * t * y2);
  }
  return steps + 1;
}

// --- piezas de la cara ---------------------------------------------------

static void drawEye(U8G2& u, float cx, float cy, float w, float h, int radius,
                    float lid_top, float lid_bot,
                    float gaze_x, float gaze_y, float pupil_r) {
  int left = (int)(cx - w / 2);
  int top  = (int)(cy - h / 2);
  int iw = (int)w, ih = (int)h;

  // ojo casi cerrado: una raya
  if (h < 2) {
    u.setDrawColor(1);
    u.drawLine(left, (int)cy, left + iw, (int)cy);
    return;
  }

  u.setDrawColor(1);
  fillRoundBox(u, left, top, iw, ih, radius);

  // pupila: hueco negro dentro del ojo blanco
  float pr = lerp(2.0f, 6.0f, pupil_r);
  float px = cx + gaze_x * (w / 2 - pr - 2);
  float py = cy - gaze_y * (h / 2 - pr - 2);
  if (h > pr * 2 + 2) {
    u.setDrawColor(0);
    u.drawDisc((int)px, (int)py, (int)pr);
  }

  // parpados: cajas negras encima. Literalmente dibujar y borrar, igual que
  // en la OLED, por eso el simulador no miente.
  if (lid_top > 0.01f) {
    int cover = (int)(h * lid_top) + 1;
    u.setDrawColor(0);
    fillBox(u, left - 1, top - 1, iw + 2, cover);
  }
  if (lid_bot > 0.01f) {
    int cover = (int)(h * lid_bot * 0.6f) + 1;
    u.setDrawColor(0);
    fillBox(u, left - 1, top + ih - cover, iw + 2, cover + 1);
  }
  u.setDrawColor(1);
}

static void drawBrow(U8G2& u, float cx, float cy, float eye_w,
                     float height, float angle, int thickness, bool mirror) {
  float y = cy - height * 7;
  float half = eye_w / 2 + 1;
  float tilt = angle * 6;
  float x1, y1, x2, y2;
  if (mirror) { x1 = cx + half; y1 = y + tilt * 0.3f; x2 = cx - half; y2 = y - tilt; }
  else        { x1 = cx - half; y1 = y + tilt * 0.3f; x2 = cx + half; y2 = y - tilt; }
  float lo = thickness / 2.0f + 1;
  if (y1 < lo) y1 = lo;
  if (y2 < lo) y2 = lo;
  u.setDrawColor(1);
  thickLine(u, (int)x1, (int)y1, (int)x2, (int)y2, thickness);
}

static void drawMouth(U8G2& u, float cx, float cy, const FaceParams& p) {
  float w = lerp(18.0f, 52.0f, p.mouth_w);
  int th = (int)lerp(1.0f, 4.0f, p.mouth_weight);
  if (th < 1) th = 1;
  float open_h = p.mouth_open * 20.0f;
  float curve  = p.mouth_curve * 11.0f;

  float left  = cx - w / 2;
  float right = cx + w / 2;
  float corner_l = -p.mouth_corner_l * 4;
  float corner_r = -p.mouth_corner_r * 4;

  if (open_h > 0.0f && open_h < 4.0f) open_h = 4.0f;  // == max(open_h, 4)

  if (open_h < 2.5f) {
    // boca cerrada: una curva
    int xs[16], ys[16];
    int n = quad(left, cy + corner_l, cx, cy + curve, right, cy + corner_r, xs, ys);
    u.setDrawColor(1);
    for (int i = 0; i < n - 1; i++) thickLine(u, xs[i], ys[i], xs[i + 1], ys[i + 1], th);
    return;
  }

  // boca abierta: dos curvas unidas, relleno blanco
  int txs[16], tys[16], bxs[16], bys[16];
  int tn = quad(left,  cy + corner_l, cx, cy + curve * 0.4f, right, cy + corner_r, txs, tys);
  int bn = quad(right, cy + corner_r, cx, cy + open_h + curve * 0.3f, left, cy + corner_l, bxs, bys);

  int xs[40], ys[40], n = 0;
  for (int i = 0; i < tn; i++) { xs[n] = txs[i]; ys[n] = tys[i]; n++; }
  for (int i = 0; i < bn; i++) { xs[n] = bxs[i]; ys[n] = bys[i]; n++; }
  u.setDrawColor(1);
  fillPolygon(u, xs, ys, n);
}

// --- entrada -------------------------------------------------------------

void faceRender(U8G2& u, const FaceParams& p) {
  u.clearBuffer();
  u.setDrawColor(1);

  float cx = W / 2 + p.face_x * 6;
  float cy = H / 2 + p.face_y * 4;

  // geometria de los ojos
  float spacing = lerp(24, 40, p.eye_spacing);
  float eye_w = lerp(16, 30, p.eye_w);
  float eye_h = lerp(10, 26, p.eye_h);
  eye_h *= (1.0f - p.squint * 0.45f);
  int radius = (int)(fminf(eye_w, eye_h) / 2 * p.eye_round);

  float eye_cy = cy - 6;
  float lx = cx - spacing / 2;
  float rx = cx + spacing / 2;
  float tilt = p.tilt * 4;

  drawEye(u, lx, eye_cy - tilt, eye_w, eye_h, radius,
          p.lid_top_l, p.lid_bot_l, p.gaze_x, p.gaze_y, p.pupil_r);
  drawEye(u, rx, eye_cy + tilt, eye_w, eye_h, radius,
          p.lid_top_r, p.lid_bot_r, p.gaze_x, p.gaze_y, p.pupil_r);

  int brow_th = (int)lerp(1, 4, p.brow_weight);
  if (brow_th < 1) brow_th = 1;
  drawBrow(u, lx, eye_cy - eye_h / 2 - 6 - tilt, eye_w,
           p.brow_l_y, p.brow_l_angle, brow_th, false);
  drawBrow(u, rx, eye_cy - eye_h / 2 - 6 + tilt, eye_w,
           p.brow_r_y, p.brow_r_angle, brow_th, true);

  drawMouth(u, cx, cy + 18, p);
}
