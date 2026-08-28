// MrRoboto - Paso 1 (+ WiFi/OTA): prueba de vida del cuerpo.
//
// Objetivo: confirmar que (a) el ESP32 corre nuestro codigo, (b) la OLED
// SH1106 esta viva en el bus I2C, y (c) la placa se une al WiFi para poder
// reflashear por aire (OTA) de aqui en adelante.
//
// Regla del proyecto: el cuerpo es un periferico. Aqui no hay ninguna
// decision, solo verificacion de hardware y plomeria de red.

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include "secrets.h"

// LED integrado de la placa DevKit (WROOM-32). Sirve de latido: si parpadea,
// el firmware esta corriendo su loop y no se ha colgado.
static const int PIN_LED = 2;

// Pines I2C por defecto del ESP32:  SDA -> GPIO21   SCL -> GPIO22
// (Se probo tambien 16/17 durante el diagnostico de la primera OLED, que
// resulto estar muerta. El ESP32 esta sano; volvemos al default estandar.)
static const int PIN_SDA = 21;
static const int PIN_SCL = 22;

// Comprueba el estado electrico de las lineas ANTES de arrancar el bus.
// En reposo, con pull-ups sanos, SDA y SCL deben leerse en ALTO. Si alguna
// se lee en BAJO, el bus esta "atascado": cable suelto, sin pull-up, o corto
// a masa. Esto distingue un problema de cableado de un problema de protocolo.
static void diagnosticoLineas() {
  pinMode(PIN_SDA, INPUT_PULLUP);
  pinMode(PIN_SCL, INPUT_PULLUP);
  delay(5);
  int sda = digitalRead(PIN_SDA);
  int scl = digitalRead(PIN_SCL);
  Serial.printf("[i2c] reposo: SDA=%s  SCL=%s\n",
                sda ? "ALTO(ok)" : "BAJO(!!)",
                scl ? "ALTO(ok)" : "BAJO(!!)");
  if (!sda || !scl) {
    Serial.println(F("[i2c]   una linea esta en BAJO -> cable suelto, sin"));
    Serial.println(F("[i2c]   pull-up o corto. Revisa ESA linea."));
  }
}

// Recorre las 127 direcciones validas del bus y reporta cuales contestan.
// La SH1106 suele estar en 0x3C (a veces 0x3D). No asumimos nada.
static void escanearI2C() {
  Serial.println(F("[i2c] escaneando bus..."));
  int encontrados = 0;

  for (uint8_t dir = 1; dir < 127; dir++) {
    Wire.beginTransmission(dir);
    uint8_t error = Wire.endTransmission();

    if (error == 0) {
      Serial.printf("[i2c]   dispositivo en 0x%02X", dir);
      if (dir == 0x3C || dir == 0x3D) {
        Serial.print(F("  <- probablemente la OLED SH1106"));
      }
      Serial.println();
      encontrados++;
    } else if (error != 2) {
      // error 2 = NACK de direccion = "nadie ahi" (normal al escanear).
      // Cualquier otro codigo (4=bus, 5=timeout) huele a linea atascada.
      Serial.printf("[i2c]   0x%02X: error de bus (codigo %d)\n", dir, error);
    }
  }

  if (encontrados == 0) {
    Serial.println(F("[i2c]   nada respondio. Revisa cableado y alimentacion."));
  } else {
    Serial.printf("[i2c] fin: %d dispositivo(s).\n", encontrados);
  }
}

// Conecta al WiFi con un limite de tiempo. NO bloquea para siempre: si la red
// no aparece, seguimos con el escaneo I2C igual (el cuerpo no depende de la
// red para estar vivo). Devuelve true si conecto.
static bool conectarWiFi() {
  Serial.printf("[wifi] conectando a \"%s\" ...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // sin modem-sleep: la placa queda siempre alcanzable
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

// Prepara el flasheo por aire. Solo tiene sentido si hay WiFi.
static void iniciarOTA() {
  ArduinoOTA.setHostname(OTA_HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);

  ArduinoOTA.onStart([]() { Serial.println(F("[ota] recibiendo firmware...")); });
  ArduinoOTA.onEnd([]()   { Serial.println(F("\n[ota] hecho, reiniciando."));   });
  ArduinoOTA.onProgress([](unsigned int hecho, unsigned int total) {
    Serial.printf("[ota] %u%%\r", (hecho * 100) / total);
  });
  ArduinoOTA.onError([](ota_error_t e) {
    Serial.printf("[ota] error %u\n", e);
  });

  ArduinoOTA.begin();
  Serial.printf("[ota] listo como \"%s.local\"\n", OTA_HOSTNAME);
}

static bool hayWiFi = false;

void setup() {
  pinMode(PIN_LED, OUTPUT);

  Serial.begin(115200);
  delay(200);  // deja que el puerto serie se estabilice tras el reset

  Serial.println();
  Serial.println(F("=================================="));
  Serial.println(F(" MrRoboto - firmware del cuerpo"));
  Serial.println(F(" Paso 1: blink + escaneo I2C + OTA"));
  Serial.println(F("=================================="));

  // Red primero, para tener OTA disponible cuanto antes.
  hayWiFi = conectarWiFi();
  if (hayWiFi) iniciarOTA();

  // Chequeo de lineas antes de tocar el bus.
  diagnosticoLineas();

  Serial.printf("[i2c] usando SDA=GPIO%d  SCL=GPIO%d\n", PIN_SDA, PIN_SCL);

  // Bus I2C a 100 kHz (standard mode). Bajamos desde 400 kHz porque con
  // jumpers dupont largos la capacitancia redondea los flancos y el bus
  // falla aunque el cableado sea correcto. Con cables cortos se puede subir.
  Wire.begin(PIN_SDA, PIN_SCL, 100000);

  escanearI2C();
}

void loop() {
  // OTA se atiende en cada vuelta: el loop es NO bloqueante para que un
  // flasheo por aire no tenga que esperar a un delay().
  if (hayWiFi) ArduinoOTA.handle();

  // Latido no bloqueante: pulso corto de 100 ms cada segundo. Se distingue
  // a ojo de un cuelgue (LED fijo o apagado).
  static uint32_t tLed = 0;
  static bool ledOn = false;
  uint32_t ahora = millis();
  if (!ledOn && ahora - tLed >= 900) { ledOn = true;  tLed = ahora; digitalWrite(PIN_LED, HIGH); }
  if (ledOn  && ahora - tLed >= 100) { ledOn = false; tLed = ahora; digitalWrite(PIN_LED, LOW);  }

  // Re-escaneo periodico: enchufa/desenchufa la OLED y ve el bus reaccionar
  // sin resetear la placa.
  static uint32_t tScan = 0;
  if (ahora - tScan > 5000) {
    tScan = ahora;
    escanearI2C();
  }
}
