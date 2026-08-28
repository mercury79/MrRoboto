// MrRoboto - Paso 2: la cara en la pantalla.
//
// Porta el motor de dibujo (face_render) a U8g2 y muestra una cara estatica
// en la SH1106. Sin capas de vida todavia (eso es el paso 3): aqui solo se
// valida que el vector facial se dibuja correcto en el hardware.
//
// Regla del proyecto: el cuerpo es un periferico. Ninguna decision aqui.

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <U8g2lib.h>
#include "secrets.h"
#include "face_params.h"
#include "face_render.h"

static const int PIN_LED = 2;
static const int PIN_SDA = 21;
static const int PIN_SCL = 22;

// SH1106 128x64 por I2C hardware, buffer COMPLETO (_F_): el render perfora
// negro sobre blanco (pupilas, parpados) y eso exige el buffer entero.
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);

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

// Cara de prueba del paso 2: neutra pero con una sonrisa suave, para ver de
// un vistazo ojos + pupilas + la curva de la boca. Es solo un preset del
// vector; cualquier otra cara es cambiar estos numeros.
static FaceParams caraDePrueba() {
  FaceParams p;                 // arranca en la neutra por defecto
  p.mouth_curve = 0.35f;        // sonrisa leve
  p.mouth_w     = 0.6f;
  return p;
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  delay(200);

  Serial.println();
  Serial.println(F("=================================="));
  Serial.println(F(" MrRoboto - firmware del cuerpo"));
  Serial.println(F(" Paso 2: la cara en la pantalla"));
  Serial.println(F("=================================="));

  hayWiFi = conectarWiFi();
  if (hayWiFi) iniciarOTA();

  // Arranca la pantalla. U8g2 usa Wire por debajo (pines por defecto 21/22).
  Wire.begin(PIN_SDA, PIN_SCL);
  u8g2.setI2CAddress(0x3C << 1);   // SH1106 en 0x3C
  bool ok = u8g2.begin();
  u8g2.setBusClock(100000);        // 100 kHz por los jumpers dupont largos
  Serial.printf("[oled] u8g2.begin() = %s\n", ok ? "OK" : "FALLO");

  // Dibuja la cara de prueba y vuelca al panel.
  faceRender(u8g2, caraDePrueba());
  u8g2.sendBuffer();
  Serial.println(F("[oled] cara dibujada."));
}

void loop() {
  if (hayWiFi) ArduinoOTA.handle();

  // Latido no bloqueante (firmware vivo). La cara es estatica en este paso.
  static uint32_t tLed = 0;
  static bool ledOn = false;
  uint32_t ahora = millis();
  if (!ledOn && ahora - tLed >= 900) { ledOn = true;  tLed = ahora; digitalWrite(PIN_LED, HIGH); }
  if (ledOn  && ahora - tLed >= 100) { ledOn = false; tLed = ahora; digitalWrite(PIN_LED, LOW);  }
}
