// Motor facial: estado emocional + capas de vida. Traduccion de
// face/engine.py.
//
// Las "capas de vida" son lo que separa una cara viva de un dibujo: parpadeo
// estocastico, sacadas y respiracion, corriendo a ~30 Hz aunque no pase
// absolutamente nada. Aunque no pase nada, algo pasa.
//
// Estas capas van EN EL FIRMWARE, no en el backend: si dependieran de la red,
// un lag de 200 ms congelaria la cara a media palabra. El backend manda
// intencion (quimica / boca); el firmware la mantiene viva.

#pragma once
#include "face_params.h"

class FaceEngine {
 public:
  FaceEngine();

  // --- intencion (lo que el backend mueve por HTTP en el paso 4) ---
  void setChem(float s, float n, float d);          // fija el estado quimico
  void nudge(float ds, float dn, float dd);         // empujon relativo
  bool applyVoiceTag(const char* tag);              // [laughs], [sighs], ...
  bool setPreset(const char* name);                 // fija la quimica de una emocion
  void setMouth(float value);                        // envolvente RMS 0..1
  void look(float x, float y);                        // dirige la mirada (-1..1)
  void wave();                                        // saludo: chispa de entusiasmo
  const char* emotionLabel() const;                  // esquina dominante (debug)

  // Lectura del estado quimico actual (para HTTP parcial y para /status).
  float chemS() const { return serotonina_; }
  float chemN() const { return noradrenalina_; }
  float chemD() const { return dopamina_; }

  // Avanza dt segundos y devuelve la cara ya con capas de vida encima.
  FaceParams update(float dt);

 private:
  // estado quimico + homeostasis
  float serotonina_, noradrenalina_, dopamina_;
  float baseS_, baseN_, baseD_, decayRate_;

  // suavizado hacia la cara objetivo
  FaceParams current_;
  float smoothing_;

  // parpadeo
  float blinkT_, blinkDur_, nextBlink_;
  // sacadas
  float gazeX_, gazeY_, gazeTx_, gazeTy_, nextSaccade_;
  // mirada dirigida (/look): sesgo que decae solo hacia el centro
  float lookX_, lookY_, lookReturn_;
  // respiracion
  float breathPhase_, breathHz_;
  // boca por voz
  float mouth_, mouthTarget_, lastMouthUpdate_, mouthWatchdog_;

  float t_;

  float scheduleBlink();
  void updateBlink(float dt);
  float blinkAmount() const;
  void updateSaccades(float dt);
};
