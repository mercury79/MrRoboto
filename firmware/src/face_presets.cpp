// Datos de presets + cubo de Lovheim. Traduccion 1:1 de face/presets.py.
// Los numeros son EXACTAMENTE los mismos que en Python: si cambias uno alla,
// cambialo aqui. Esta es la fuente de intencion; las capas de vida (parpadeo,
// sacadas, respiracion) se suman encima en face_engine.

#include "face_presets.h"
#include <string.h>

// --- presets emocionales -------------------------------------------------
// Cada uno arranca del FaceParams neutro (defaults del struct) y solo toca los
// campos que la emocion mueve, igual que los kwargs de Python.

FaceParams preset_reposo() {
  FaceParams p;
  p.brow_l_y = 0.05f; p.brow_r_y = 0.05f;
  p.eye_w = 0.55f; p.eye_h = 0.55f; p.eye_round = 0.65f;
  p.lid_bot_l = 0.10f; p.lid_bot_r = 0.10f;
  p.pupil_r = 0.5f;
  p.mouth_curve = 0.40f; p.mouth_w = 0.45f; p.mouth_open = 0.0f; p.mouth_weight = 0.5f;
  return p;
}

static FaceParams preset_alegria() {
  FaceParams p;
  p.brow_l_y = 0.35f; p.brow_r_y = 0.35f;
  p.eye_w = 0.6f; p.eye_h = 0.45f; p.eye_round = 0.8f;
  p.lid_bot_l = 0.45f; p.lid_bot_r = 0.45f;   // el ojo que sonrie sube el parpado de abajo
  p.pupil_r = 0.7f;
  p.mouth_curve = 0.9f; p.mouth_w = 0.7f; p.mouth_open = 0.35f; p.mouth_weight = 0.6f;
  p.mouth_corner_l = 0.5f; p.mouth_corner_r = 0.5f;
  return p;
}

static FaceParams preset_interes() {
  FaceParams p;
  p.brow_l_y = 0.5f; p.brow_r_y = 0.35f;      // asimetrica: una ceja mas alta
  p.brow_l_angle = 0.1f;
  p.eye_w = 0.65f; p.eye_h = 0.7f; p.eye_round = 0.7f;
  p.pupil_r = 0.75f;
  p.gaze_y = 0.1f;
  p.mouth_curve = 0.45f; p.mouth_w = 0.45f; p.mouth_open = 0.12f;
  p.tilt = 0.15f;
  return p;
}

static FaceParams preset_sorpresa() {
  FaceParams p;
  p.brow_l_y = 0.95f; p.brow_r_y = 0.95f;
  p.eye_w = 0.75f; p.eye_h = 0.95f; p.eye_round = 0.95f;
  p.pupil_r = 0.9f;
  p.mouth_open = 0.7f; p.mouth_w = 0.35f; p.mouth_curve = 0.0f;
  return p;
}

static FaceParams preset_enojo() {
  FaceParams p;
  p.brow_l_y = -0.8f; p.brow_r_y = -0.8f;
  p.brow_l_angle = -0.9f; p.brow_r_angle = -0.9f;
  p.brow_weight = 0.9f;
  p.eye_w = 0.6f; p.eye_h = 0.4f;
  p.squint = 0.5f;
  p.pupil_r = 0.3f;
  p.mouth_curve = -0.60f; p.mouth_w = 0.55f; p.mouth_weight = 0.7f; p.mouth_open = 0.0f;
  return p;
}

static FaceParams preset_miedo() {
  FaceParams p;
  p.brow_l_y = 0.8f; p.brow_r_y = 0.8f;
  p.brow_l_angle = 0.6f; p.brow_r_angle = 0.6f;
  p.eye_w = 0.7f; p.eye_h = 0.9f; p.eye_round = 0.9f;
  p.pupil_r = 0.95f;
  p.gaze_x = -0.3f;
  p.mouth_open = 0.45f; p.mouth_w = 0.6f; p.mouth_curve = -0.35f;
  return p;
}

static FaceParams preset_desagrado() {
  FaceParams p;
  p.brow_l_y = -0.4f; p.brow_r_y = -0.25f;
  p.brow_l_angle = -0.4f;
  p.eye_w = 0.5f; p.eye_h = 0.35f;
  p.squint = 0.75f;
  p.pupil_r = 0.35f;
  p.mouth_curve = -0.3f; p.mouth_w = 0.4f; p.mouth_open = 0.1f;
  p.mouth_corner_l = 0.4f; p.mouth_corner_r = -0.5f;   // asimetrica: media boca arriba
  p.tilt = -0.1f;
  return p;
}

static FaceParams preset_verguenza() {
  FaceParams p;
  p.brow_l_y = -0.1f; p.brow_r_y = -0.1f;
  p.brow_l_angle = 0.4f; p.brow_r_angle = 0.4f;
  p.eye_w = 0.45f; p.eye_h = 0.4f;
  p.lid_top_l = 0.5f; p.lid_top_r = 0.5f;
  p.pupil_r = 0.4f;
  p.gaze_x = -0.5f; p.gaze_y = -0.6f;
  p.mouth_curve = -0.2f; p.mouth_w = 0.35f;
  p.face_y = -0.15f;
  return p;
}

static FaceParams preset_angustia() {
  FaceParams p;
  p.brow_l_y = 0.2f; p.brow_r_y = 0.2f;
  p.brow_l_angle = 0.9f; p.brow_r_angle = 0.9f;
  p.eye_w = 0.55f; p.eye_h = 0.6f;
  p.lid_top_l = 0.2f; p.lid_top_r = 0.2f;
  p.pupil_r = 0.6f;
  p.gaze_y = -0.2f;
  p.mouth_curve = -0.8f; p.mouth_w = 0.5f; p.mouth_open = 0.25f;
  return p;
}

// --- cubo de Lovheim -----------------------------------------------------
//
// Ejes: serotonina (S), noradrenalina (NA), dopamina (DA), cada uno 0..1.
// Las 8 esquinas, en el orden de bits (S,NA,DA):
//
//   S NA DA  emocion
//   0  0  0  verguenza
//   0  0  1  desagrado
//   0  1  0  angustia
//   0  1  1  enojo
//   1  0  0  miedo
//   1  0  1  alegria
//   1  1  0  sorpresa
//   1  1  1  interes
//
// (En este modelo el miedo NO cae en noradrenalina alta: contraintuitivo pero
// es lo que dice Lovheim.)

struct Corner { int s, n, d; const char* name; FaceParams (*make)(); };

// Cada esquina apunta a su preset. El orden es el de bits (S,NA,DA).
static const Corner CUBE[8] = {
  {0, 0, 0, "verguenza", preset_verguenza},
  {0, 0, 1, "desagrado", preset_desagrado},
  {0, 1, 0, "angustia",  preset_angustia},
  {0, 1, 1, "enojo",     preset_enojo},
  {1, 0, 0, "miedo",     preset_miedo},
  {1, 0, 1, "alegria",   preset_alegria},
  {1, 1, 0, "sorpresa",  preset_sorpresa},
  {1, 1, 1, "interes",   preset_interes},
};

static float corner_weight(const Corner& c, float s, float n, float d) {
  return (c.s ? s : 1.0f - s) * (c.n ? n : 1.0f - n) * (c.d ? d : 1.0f - d);
}

FaceParams from_lovheim(float serotonina, float noradrenalina, float dopamina) {
  float s = clamp01(serotonina), n = clamp01(noradrenalina), d = clamp01(dopamina);
  FaceParams caras[8];
  float pesos[8];
  float total = 0.0f;
  for (int i = 0; i < 8; i++) {
    caras[i] = CUBE[i].make();
    pesos[i] = corner_weight(CUBE[i], s, n, d);
    total += pesos[i];
  }
  if (total <= 0.001f) return preset_reposo();
  return blend_many(caras, pesos, 8);   // blend_many normaliza los pesos
}

const char* dominant_emotion(float serotonina, float noradrenalina, float dopamina) {
  float s = clamp01(serotonina), n = clamp01(noradrenalina), d = clamp01(dopamina);
  const char* best = "reposo";
  float best_w = -1.0f;
  for (int i = 0; i < 8; i++) {
    float w = corner_weight(CUBE[i], s, n, d);
    if (w > best_w) { best_w = w; best = CUBE[i].name; }
  }
  return best;
}

// --- etiquetas de voz ----------------------------------------------------

struct VoiceTag { const char* tag; float ds, dn, dd; };

static const VoiceTag VOICE_TAGS[] = {
  {"[laughs]",    0.15f, -0.05f,  0.25f},
  {"[chuckles]",  0.10f, -0.05f,  0.15f},
  {"[sighs]",    -0.15f, -0.10f, -0.20f},
  {"[gasps]",     0.05f,  0.35f,  0.05f},
  {"[whispers]",  0.00f, -0.15f, -0.05f},
  {"[excited]",   0.10f,  0.25f,  0.30f},
  {"[sad]",      -0.25f,  0.05f, -0.25f},
  {"[angry]",    -0.35f,  0.30f,  0.20f},
  {"[curious]",   0.10f,  0.20f,  0.15f},
};
static const int N_VOICE_TAGS = sizeof(VOICE_TAGS) / sizeof(VOICE_TAGS[0]);

bool voice_tag_delta(const char* tag, float* ds, float* dn, float* dd) {
  for (int i = 0; i < N_VOICE_TAGS; i++) {
    if (strcmp(tag, VOICE_TAGS[i].tag) == 0) {
      *ds = VOICE_TAGS[i].ds; *dn = VOICE_TAGS[i].dn; *dd = VOICE_TAGS[i].dd;
      return true;
    }
  }
  return false;
}
