// Renderer: traduccion de face/render.py a U8g2.
//
// Dibuja el vector facial en el buffer de U8g2 (128x64, 1 bit). NO llama a
// sendBuffer(): el que llama decide cuando volcar a la pantalla (asi el
// paso 3 podra componer capas antes de mostrar).
//
// Requiere un U8G2 en modo FULL buffer (_F_): el render dibuja blanco y
// luego perfora negro (pupilas, parpados), y eso necesita el buffer completo.

#pragma once
#include <U8g2lib.h>
#include "face_params.h"

void faceRender(U8G2& u8g2, const FaceParams& p);
