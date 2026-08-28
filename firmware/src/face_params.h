// Espejo EXACTO de la dataclass FaceParams de face/params.py.
//
// Mismos campos, mismo orden. NO reordenar: el orden es el contrato con el
// backend (as_list en Python) y con blend(). Si cambias params.py, cambia
// aqui igual y en el mismo lugar.
//
// La cara no son dibujos por emocion: es este vector continuo. Cada emocion
// es un preset de estos numeros, y cualquier punto intermedio es valido.

#pragma once
#include <math.h>

struct FaceParams {
  // --- Cejas (5) ---
  float brow_l_y     = 0.0f;   // -1 hundida (enojo) .. +1 levantada (sorpresa)
  float brow_r_y     = 0.0f;
  float brow_l_angle = 0.0f;   // -1 punta interna abajo .. +1 arriba (tristeza)
  float brow_r_angle = 0.0f;
  float brow_weight  = 0.5f;   // 0 fina .. 1 gruesa

  // --- Parpados (4) ---
  float lid_top_l = 0.0f;      // 0 abierto .. 1 cerrado del todo
  float lid_top_r = 0.0f;
  float lid_bot_l = 0.0f;      // parpado inferior: sube al sonreir de verdad
  float lid_bot_r = 0.0f;

  // --- Ojos (4) ---
  float eye_w       = 0.5f;    // 0 angosto .. 1 ancho
  float eye_h       = 0.5f;    // 0 aplastado .. 1 alto
  float eye_round   = 0.6f;    // 0 rectangular .. 1 circular
  float eye_spacing = 0.5f;    // separacion entre ojos

  // --- Pupilas / mirada (4) ---
  float pupil_r = 0.5f;        // 0 contraida .. 1 dilatada
  float gaze_x  = 0.0f;        // -1 izquierda .. +1 derecha
  float gaze_y  = 0.0f;        // -1 abajo .. +1 arriba
  float squint  = 0.0f;        // 0 nada .. 1 entrecerrado (desconfianza)

  // --- Boca (6) ---
  float mouth_open     = 0.0f; // 0 cerrada .. 1 abierta al maximo
  float mouth_w        = 0.5f; // ancho
  float mouth_curve    = 0.0f; // -1 hacia abajo .. +1 sonrisa
  float mouth_corner_l = 0.0f; // asimetria: -1 comisura abajo .. +1 arriba
  float mouth_corner_r = 0.0f;
  float mouth_weight   = 0.5f; // grosor del trazo

  // --- Global (3) ---
  float face_x = 0.0f;         // desplazamiento lateral (sway)
  float face_y = 0.0f;         // desplazamiento vertical (respiracion)
  float tilt   = 0.0f;         // -1 .. +1 inclinacion

  // Numero de campos == len(FaceParams.field_names()) en Python.
  static constexpr int N = 26;

  // Acceso al vector como arreglo, en el orden estable de params.py.
  // Todos los campos son float contiguos: esto es el as_list() del firmware.
  float*       data()       { return &brow_l_y; }
  const float* data() const { return &brow_l_y; }
  float& operator[](int i)       { return data()[i]; }
  float  operator[](int i) const { return data()[i]; }

  // Interpolacion lineal campo a campo (== FaceParams.blend en Python).
  FaceParams blend(const FaceParams& other, float t) const {
    if (t < 0.0f) t = 0.0f; else if (t > 1.0f) t = 1.0f;
    FaceParams out;
    const float* a = data();
    const float* b = other.data();
    for (int i = 0; i < N; i++) out[i] = a[i] + (b[i] - a[i]) * t;
    return out;
  }
};

// Si algun campo dejara de ser float (o se colara padding), el orden-como-
// arreglo se rompe silenciosamente. Esto lo convierte en error de compilacion.
static_assert(sizeof(FaceParams) == FaceParams::N * sizeof(float),
              "FaceParams debe ser N floats contiguos, sin padding");

// Mezcla ponderada de varias caras (== blend_many de params.py).
// Arreglos paralelos: caras[i] con peso pesos[i], longitud n. Pesos se
// normalizan. Si suman <= 0, devuelve la cara neutra por defecto.
inline FaceParams blend_many(const FaceParams* caras, const float* pesos, int n) {
  float total = 0.0f;
  for (int i = 0; i < n; i++) total += pesos[i];
  FaceParams out;
  if (total <= 0.0f) return out;
  for (int f = 0; f < FaceParams::N; f++) {
    float acc = 0.0f;
    for (int i = 0; i < n; i++) acc += caras[i][f] * pesos[i];
    out[f] = acc / total;
  }
  return out;
}
