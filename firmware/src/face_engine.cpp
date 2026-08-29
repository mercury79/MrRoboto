// Motor facial. Traduccion 1:1 de face/engine.py.
//
// Diferencia con el simulador: aqui el RNG es el hardware del ESP32
// (esp_random), no una semilla fija. La cara nunca parpadea igual dos veces,
// que es justo lo que queremos.

#include "face_engine.h"
#include "face_presets.h"
#include <math.h>
#include <esp_system.h>   // esp_random()

static const float TAU = 6.28318530717958647692f;

// --- RNG -----------------------------------------------------------------

static inline float randf() {                 // [0, 1)
  return (float)esp_random() / 4294967296.0f;
}
static inline float uniformf(float a, float b) {
  return a + (b - a) * randf();
}
static float gaussf(float mu, float sigma) {  // Box-Muller con reserva
  static bool haveSpare = false;
  static float spare = 0.0f;
  if (haveSpare) { haveSpare = false; return mu + sigma * spare; }
  float u1;
  do { u1 = randf(); } while (u1 < 1e-7f);
  float u2 = randf();
  float mag = sqrtf(-2.0f * logf(u1));
  spare = mag * sinf(TAU * u2);
  haveSpare = true;
  return mu + sigma * mag * cosf(TAU * u2);
}
static inline float expovariatef(float lambd) {
  float u = randf();                          // [0,1) -> 1-u en (0,1]
  return -logf(1.0f - u) / lambd;
}

static inline float clampSym(float x) {
  return x < -1.0f ? -1.0f : (x > 1.0f ? 1.0f : x);
}

// --- construccion --------------------------------------------------------

FaceEngine::FaceEngine() {
  // Estado quimico. Arranca en la esquina de alegria pero moderado: la cara de
  // reposo es contenta, no neutra.
  serotonina_ = 0.70f; noradrenalina_ = 0.30f; dopamina_ = 0.60f;
  baseS_ = 0.70f; baseN_ = 0.30f; baseD_ = 0.60f;
  decayRate_ = 0.12f;                 // por segundo, hacia el baseline

  current_ = from_lovheim(serotonina_, noradrenalina_, dopamina_);
  smoothing_ = 7.0f;                  // mayor = mas rapido

  blinkT_ = 0.0f; blinkDur_ = 0.0f; nextBlink_ = scheduleBlink();

  gazeX_ = gazeY_ = gazeTx_ = gazeTy_ = 0.0f;
  nextSaccade_ = uniformf(0.4f, 1.6f);

  breathPhase_ = uniformf(0.0f, TAU);
  breathHz_ = 0.22f;

  mouth_ = 0.0f; mouthTarget_ = 0.0f; lastMouthUpdate_ = 0.0f;
  mouthWatchdog_ = 0.400f;            // s: si muere el stream, la boca cierra sola

  t_ = 0.0f;
}

// --- intencion -----------------------------------------------------------

void FaceEngine::setChem(float s, float n, float d) {
  serotonina_ = clamp01(s);
  noradrenalina_ = clamp01(n);
  dopamina_ = clamp01(d);
}

void FaceEngine::nudge(float ds, float dn, float dd) {
  serotonina_ = clamp01(serotonina_ + ds);
  noradrenalina_ = clamp01(noradrenalina_ + dn);
  dopamina_ = clamp01(dopamina_ + dd);
}

bool FaceEngine::applyVoiceTag(const char* tag) {
  float ds, dn, dd;
  if (voice_tag_delta(tag, &ds, &dn, &dd)) { nudge(ds, dn, dd); return true; }
  return false;
}

void FaceEngine::setMouth(float value) {
  mouthTarget_ = clamp01(value);
  lastMouthUpdate_ = t_;
}

const char* FaceEngine::emotionLabel() const {
  return dominant_emotion(serotonina_, noradrenalina_, dopamina_);
}

// --- capas de vida -------------------------------------------------------

float FaceEngine::scheduleBlink() {
  // Los parpadeos humanos no son periodicos: se agrupan. Distribucion sesgada
  // a intervalos cortos con cola larga.
  float base = expovariatef(1.0f / 3.2f);
  if (base < 0.8f) base = 0.8f;
  if (base > 9.0f) base = 9.0f;
  return base;
}

void FaceEngine::updateBlink(float dt) {
  nextBlink_ -= dt;
  if (blinkDur_ > 0.0f) {
    blinkT_ += dt;
    if (blinkT_ >= blinkDur_) { blinkDur_ = 0.0f; blinkT_ = 0.0f; }
  } else if (nextBlink_ <= 0.0f) {
    blinkDur_ = uniformf(0.09f, 0.16f);
    blinkT_ = 0.0f;
    nextBlink_ = scheduleBlink();
    if (randf() < 0.18f) nextBlink_ = uniformf(0.25f, 0.5f);  // a veces doble
  }
}

float FaceEngine::blinkAmount() const {
  // 0 = ojo abierto, 1 = cerrado. Cierre rapido, apertura mas lenta.
  if (blinkDur_ <= 0.0f) return 0.0f;
  float p = blinkT_ / blinkDur_;
  if (p < 0.4f) return powf(p / 0.4f, 0.7f);
  return powf(1.0f - (p - 0.4f) / 0.6f, 1.6f);
}

void FaceEngine::updateSaccades(float dt) {
  nextSaccade_ -= dt;
  if (nextSaccade_ <= 0.0f) {
    if (randf() < 0.15f) {                    // salto grande de vez en cuando
      gazeTx_ = uniformf(-0.8f, 0.8f);
      gazeTy_ = uniformf(-0.5f, 0.5f);
      nextSaccade_ = uniformf(1.0f, 3.0f);
    } else {                                  // micro-dardos casi siempre
      gazeTx_ = clampSym(gazeTx_ + gaussf(0.0f, 0.12f));
      gazeTy_ = clampSym(gazeTy_ + gaussf(0.0f, 0.07f));
      nextSaccade_ = uniformf(0.25f, 1.1f);
    }
  }
  // las sacadas son casi instantaneas: ~40 ms
  float k = dt / 0.04f; if (k > 1.0f) k = 1.0f;
  gazeX_ += (gazeTx_ - gazeX_) * k;
  gazeY_ += (gazeTy_ - gazeY_) * k;
}

// --- update ---------------------------------------------------------------

FaceParams FaceEngine::update(float dt) {
  t_ += dt;

  // homeostasis: la quimica vuelve sola al baseline
  float k = decayRate_ * dt; if (k > 1.0f) k = 1.0f;
  serotonina_    += (baseS_ - serotonina_)    * k;
  noradrenalina_ += (baseN_ - noradrenalina_) * k;
  dopamina_      += (baseD_ - dopamina_)      * k;

  // cara objetivo segun quimica, suavizada
  FaceParams target = from_lovheim(serotonina_, noradrenalina_, dopamina_);
  float blend = smoothing_ * dt; if (blend > 1.0f) blend = 1.0f;
  current_ = current_.blend(target, blend);

  FaceParams out = current_;   // FaceParams es trivialmente copiable

  // --- capa: respiracion ---
  breathPhase_ += dt * breathHz_ * TAU;
  float breath = sinf(breathPhase_);
  out.face_y += breath * 0.06f;
  out.eye_h  += breath * 0.015f;

  // --- capa: sacadas ---
  updateSaccades(dt);
  out.gaze_x = clampSym(out.gaze_x + gazeX_ * 0.35f);
  out.gaze_y = clampSym(out.gaze_y + gazeY_ * 0.25f);

  // --- capa: parpadeo ---
  updateBlink(dt);
  float b = blinkAmount();
  if (b > 0.0f) {
    if (b > out.lid_top_l) out.lid_top_l = b;
    if (b > out.lid_top_r) out.lid_top_r = b;
  }

  // --- capa: boca por voz ---
  if (t_ - lastMouthUpdate_ > mouthWatchdog_) mouthTarget_ = 0.0f;
  float km = dt / 0.05f; if (km > 1.0f) km = 1.0f;
  mouth_ += (mouthTarget_ - mouth_) * km;
  if (mouth_ > 0.01f) {
    float m = mouth_ * 0.85f;
    if (m > out.mouth_open) out.mouth_open = m;
  }

  return out;
}
