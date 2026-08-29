// Implementacion de los verbos HTTP. Servidor sincrono (WebServer del core
// ESP32): handleClient() se llama en el loop y es instantaneo cuando no hay
// cliente, asi que no estorba a los ~30 Hz de la cara.

#include "http_api.h"
#include "face_engine.h"
#include <WebServer.h>

static WebServer server(80);
static FaceEngine* eng = nullptr;

// Lee un parametro float; 0 si no viene.
static float argf(const char* key) {
  return server.hasArg(key) ? server.arg(key).toFloat() : 0.0f;
}

// Responde el estado actual (lo que quedo tras aplicar el verbo).
static void sendState(int code) {
  char buf[200];
  snprintf(buf, sizeof(buf),
           "{\"emotion\":\"%s\",\"chem\":{\"s\":%.2f,\"n\":%.2f,\"d\":%.2f}}",
           eng->emotionLabel(), eng->chemS(), eng->chemN(), eng->chemD());
  server.send(code, "application/json", buf);
}

static void handleRoot() {
  const char* help =
    "MrRoboto - cuerpo (verbos HTTP)\n"
    "\n"
    "GET /status            estado actual (JSON)\n"
    "GET /face?preset=alegria\n"
    "GET /face?s=0.7&n=0.3&d=0.6   quimica absoluta (parcial ok)\n"
    "GET /face?ds=0.1&dd=0.2       empujon relativo\n"
    "GET /face?tag=[laughs]        etiqueta de voz\n"
    "GET /face?mouth=0.63          boca por voz (RMS 0..1)\n"
    "GET /look?x=-0.5&y=0.2        dirige la mirada (-1..1)\n"
    "GET /wave                     saludo\n"
    "\n"
    "presets: reposo alegria interes sorpresa miedo\n"
    "         enojo desagrado angustia verguenza\n";
  server.send(200, "text/plain", help);
}

static void handleFace() {
  // preset por nombre (fija la quimica de esa emocion)
  if (server.hasArg("preset")) {
    if (!eng->setPreset(server.arg("preset").c_str())) {
      server.send(400, "application/json", "{\"error\":\"preset desconocido\"}");
      return;
    }
  }

  // quimica absoluta: s/n/d. Parcial: los que no vengan se quedan como estan.
  if (server.hasArg("s") || server.hasArg("n") || server.hasArg("d")) {
    float s = server.hasArg("s") ? server.arg("s").toFloat() : eng->chemS();
    float n = server.hasArg("n") ? server.arg("n").toFloat() : eng->chemN();
    float d = server.hasArg("d") ? server.arg("d").toFloat() : eng->chemD();
    eng->setChem(s, n, d);
  }

  // empujon relativo
  if (server.hasArg("ds") || server.hasArg("dn") || server.hasArg("dd")) {
    eng->nudge(argf("ds"), argf("dn"), argf("dd"));
  }

  // etiqueta de voz ([laughs], [sighs], ...): mueve la quimica
  if (server.hasArg("tag")) {
    eng->applyVoiceTag(server.arg("tag").c_str());
  }

  // boca por voz: envolvente RMS. El watchdog del motor la cierra sola a los
  // 400 ms si el stream muere, asi que no hace falta un verbo de "cerrar".
  if (server.hasArg("mouth")) {
    eng->setMouth(server.arg("mouth").toFloat());
  }

  sendState(200);
}

static void handleLook() {
  float x = server.hasArg("x") ? server.arg("x").toFloat() : 0.0f;
  float y = server.hasArg("y") ? server.arg("y").toFloat() : 0.0f;
  eng->look(x, y);
  sendState(200);
}

static void handleWave() {
  eng->wave();
  sendState(200);
}

static void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"verbo no existe. GET / para la ayuda\"}");
}

void httpSetup(FaceEngine* engine) {
  eng = engine;
  server.on("/", handleRoot);
  server.on("/status", []() { sendState(200); });
  server.on("/face", handleFace);
  server.on("/look", handleLook);
  server.on("/wave", handleWave);
  server.onNotFound(handleNotFound);
  server.begin();
}

void httpLoop() {
  server.handleClient();
}
