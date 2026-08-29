// MrRoboto - Paso 4: la cara viva + verbos HTTP.
//
// La cara vive sola (FaceEngine: parpadeo, sacadas, respiracion a tiempo real)
// y ahora el backend puede mandarle INTENCION por HTTP (/face, /look, /wave)
// sin congelar la ilusion.
//
// Regla del proyecto: el cuerpo es un periferico. El firmware mantiene la cara
// VIVA por su cuenta; el backend solo manda intencion: mueve la quimica, la
// boca (RMS) y la mirada. Esas capas viven aqui a proposito: si dependieran de
// la red, un lag congelaria la cara a media palabra.

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <U8g2lib.h>
#include "secrets.h"
#include "face_params.h"
#include "face_render.h"
#include "face_engine.h"
#include "http_api.h"

static const int PIN_LED = 2;
static const int PIN_SDA = 21;
static const int PIN_SCL = 22;

// Reloj del bus I2C. 100 kHz es conservador por los jumpers dupont largos del
// prototipo. A 100 kHz un volcado completo (128x64) tarda ~9 ms, asi que el
// techo real ronda los ~30 fps con el resto del loop. Si el cableado lo
// aguanta, subir a 400000 da mas cuadros y las capas se ven mas suaves. La
// animacion usa dt real, asi que el TIEMPO es correcto a cualquier fps.
static const uint32_t I2C_CLOCK = 100000;

// SH1106 128x64 por I2C hardware, buffer COMPLETO (_F_): el render perfora
// negro sobre blanco (pupilas, parpados) y eso exige el buffer entero.
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);

// El motor facial: estado emocional + capas de vida. Vive en el firmware.
static FaceEngine engine;

static bool hayWiFi = false;

static bool conectarWiFi() {
  Serial.printf("[wifi] conectando a \"%s\" ...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(F("[wifi] conectado. IP: "));
    Serial.println(WiFi.localIP());
    return true;
  }
  Serial.println(F("[wifi] no conecto (timeout). Sigo sin red."));
  return false;
}

static void iniciarOTA() {
  ArduinoOTA.setHostname(OTA_HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() { Serial.println(F("[ota] recibiendo firmware...")); });
  ArduinoOTA.onEnd([]()   { Serial.println(F("\n[ota] hecho, reiniciando.")); });
  ArduinoOTA.onProgress([](unsigned int hecho, unsigned int total) {
    Serial.printf("[ota] %u%%\r", (hecho * 100) / total);
  });
  ArduinoOTA.onError([](ota_error_t e) { Serial.printf("[ota] error %u\n", e); });
  ArduinoOTA.begin();
  Serial.printf("[ota] listo como \"%s.local\"\n", OTA_HOSTNAME);
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  delay(200);

  Serial.println();
  Serial.println(F("=================================="));
  Serial.println(F(" MrRoboto - firmware del cuerpo"));
  Serial.println(F(" Paso 4: cara viva + verbos HTTP"));
  Serial.println(F("=================================="));

  hayWiFi = conectarWiFi();
  if (hayWiFi) {
    iniciarOTA();
    httpSetup(&engine);   // verbos HTTP en el puerto 80
    Serial.print(F("[http] verbos listos en http://"));
    Serial.print(WiFi.localIP());
    Serial.println(F("/  (GET / para la ayuda)"));
  }

  // Arranca la pantalla. U8g2 usa Wire por debajo (pines por defecto 21/22).
  Wire.begin(PIN_SDA, PIN_SCL);
  u8g2.setI2CAddress(0x3C << 1);   // SH1106 en 0x3C
  bool ok = u8g2.begin();
  u8g2.setBusClock(I2C_CLOCK);
  Serial.printf("[oled] u8g2.begin() = %s\n", ok ? "OK" : "FALLO");
  Serial.printf("[cara] reposo: %s\n", engine.emotionLabel());
  Serial.println(F("[cara] capas de vida activas (parpadeo, sacadas, respiracion)."));
}

void loop() {
  if (hayWiFi) { ArduinoOTA.handle(); httpLoop(); }

  // Reloj de la animacion: dt real en segundos entre cuadros. Cap suave a
  // ~60 fps por si el bus I2C se sube y el loop se dispara; el limitante
  // normal es el volcado a la pantalla, no este gate.
  static uint32_t tPrev = 0;
  uint32_t now = micros();
  if (tPrev == 0) tPrev = now;
  float dt = (now - tPrev) * 1e-6f;
  if (dt < 0.016f) return;
  tPrev = now;

  // La cara: intencion (quimica) + capas de vida, resuelto por el motor.
  FaceParams cara = engine.update(dt);
  faceRender(u8g2, cara);
  u8g2.sendBuffer();

  // Latido del firmware en el LED (breve, no bloqueante): senal de que el loop
  // corre. La cara ya demuestra que esta vivo, pero el LED sirve sin mirar.
  static uint32_t tLed = 0;
  static bool ledOn = false;
  uint32_t ms = millis();
  if (!ledOn && ms - tLed >= 900) { ledOn = true;  tLed = ms; digitalWrite(PIN_LED, HIGH); }
  if (ledOn  && ms - tLed >= 100) { ledOn = false; tLed = ms; digitalWrite(PIN_LED, LOW);  }
}
