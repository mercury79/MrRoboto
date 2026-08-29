// Presets emocionales + cubo de Lovheim. Traduccion de face/presets.py.
//
// Dos capas:
//   1. PRESETS: cada emocion es un punto del vector facial (un FaceParams).
//   2. CUBO DE LOVHEIM: el estado interno son tres numeros continuos
//      (serotonina, noradrenalina, dopamina) en 0..1. Las 8 esquinas del cubo
//      son 8 emociones basicas; cualquier punto interior se resuelve por
//      interpolacion trilineal -> una cara valida.
//
// Por eso la cara es un readout honesto del estado interno y no una animacion
// decorativa: no elegimos "cara feliz", movemos quimica y la cara cae donde
// tenga que caer.
//
// Ref: Lovheim, H. (2012). Med Hypotheses 78(2):341-8.

#pragma once
#include "face_params.h"

inline float clamp01(float x) { return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x); }

// Cara de reposo (== PRESETS["reposo"]). No es neutra, es CONTENTA: en calma
// no estamos apagados, estamos bien. Sirve de fallback.
FaceParams preset_reposo();

// Estado quimico continuo -> cara, por interpolacion trilineal en el cubo.
FaceParams from_lovheim(float serotonina, float noradrenalina, float dopamina);

// Etiqueta de la esquina mas cercana. Solo para debug/logs.
const char* dominant_emotion(float serotonina, float noradrenalina, float dopamina);

// Nombre de emocion -> quimica (S,NA,DA) que la produce. Las 8 esquinas del
// cubo dan 0/1 exactos; "reposo" da el baseline contento. Devuelve false si el
// nombre no existe. Sirve para /face?preset=alegria.
bool chem_for_name(const char* name, float* s, float* n, float* d);

// Etiquetas de voz -> empujon quimico (== VOICE_TAGS de presets.py).
// El agente escribe [laughs] en su texto: ElevenLabs lo vuelve risa y nosotros
// lo volvemos cara. Un solo token, dos efectos, cero clasificador externo.
// Devuelve true y llena ds/dn/dd si la etiqueta existe.
bool voice_tag_delta(const char* tag, float* ds, float* dn, float* dd);
