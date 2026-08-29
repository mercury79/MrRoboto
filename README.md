# MrRoboto

Cabeza robótica de escritorio con agente de IA encarnado.

Regla de diseño: **el cuerpo es un periférico.** El ESP32 no piensa, no corre
IA, no decide nada. Expone verbos HTTP y espera a que alguien los llame. La
cognición vive en el backend. Esa separación entre cognición (que cambia y
mejora) y actuación (que debe ser aburrida y confiable) es lo que hace que el
sistema no se rompa.

## Estado

Fase 1 — motor facial. Corre en la PC, sin hardware.

```
MrRoboto/
├── face/
│   ├── params.py     vector de ~25 parámetros continuos
│   ├── presets.py    presets emocionales + cubo de Lövheim
│   ├── engine.py     capas de vida + estado químico
│   └── render.py     dibujado a framebuffer 128×64, 1 bit
└── sim.py            simulador Pygame
```

## Correr

```bash
pip install -r requirements.txt
python sim.py
```

Teclas: `1`–`0` emociones · flechas y `Q`/`A` mueven la química ·
`M` enciende el micrófono (la boca sigue tu voz) · `R` reposo · `ESC` salir.

## Las tres ideas

**1. La cara es un vector, no una galería de dibujos.**
No hay un sprite por emoción. Hay ~25 parámetros continuos (cejas, párpados,
pupilas, mirada, boca) y cada emoción es un *preset* de ese vector. Cualquier
punto intermedio es una cara válida, así que los estados se mezclan en vez de
saltar.

**2. La cara sale de la química, no al revés.**
El estado interno son tres números: serotonina, noradrenalina, dopamina. Las 8
esquinas del cubo de Lövheim son las 8 emociones básicas de Tomkins, y
cualquier punto interior se resuelve por interpolación trilineal. No elegimos
"cara feliz": movemos química y la cara cae donde tenga que caer. Por eso es
un *readout* honesto y no una animación decorativa.

Las etiquetas de voz cierran el círculo: el agente escribe `[laughs]` en su
texto, ElevenLabs lo convierte en risa y nosotros lo convertimos en cara. Un
solo token, dos efectos, ningún clasificador externo adivinando.

**3. La vida corre a 30 Hz aunque no pase nada.**
Parpadeo estocástico (agrupado, no periódico), sacadas —los micro-dardos del
ojo que nunca está quieto— y respiración. Aunque no pase nada, algo pasa.

**Estas capas van en el firmware, no en el backend.** Si dependen de la red,
un lag de 200 ms congela la cara a media palabra. El backend manda intención;
el firmware la mantiene viva.

## Boca por voz

El envolvente RMS del audio en ventanas de ~150 ms, empujado a ~7 Hz, que es
la cadencia silábica del habla. Más rápido tiembla, más lento se ve como
doblaje mal sincronizado. En el robot habrá que **adelantarlo ~120 ms** para
compensar el viaje hasta la placa; en el simulador no hace falta porque el
render es local.

El firmware cierra la boca solo a los **400 ms** si el stream muere, en vez de
quedarse congelada a media palabra.

## Por qué el simulador es 128×64 de un bit

Porque la SH1106 es 128×64 de un bit: blanco o negro, sin grises, sin trampa.
Si algo no se ve bien en la ventana, tampoco se va a ver en el hardware. El
escalado es *nearest-neighbor* a propósito — queremos ver los píxeles.

`render.py` es el archivo que se traduce a C++ cuando llegue el ESP32.
Las primitivas tienen equivalente directo en U8g2 (`drawBox`, `drawDisc`,
`drawLine`), y el orden de campos de `FaceParams` es el mismo que tendrá el
struct del firmware.

## Firmware (ESP32)

El cuerpo corre en un ESP32 con la SH1106. `render.py` y `engine.py` se
tradujeron a C++ campo por campo — mismo vector, mismas capas.

- [x] Paso 1 — base: blink, escaneo I2C, WiFi y OTA
- [x] Paso 2 — port del motor de dibujo a U8g2 (cara estática)
- [x] Paso 3 — capas de vida en el firmware (parpadeo, sacadas, respiración)
- [x] Paso 4 — verbos HTTP: `/face`, `/look`, `/wave`

### Verbos HTTP

El cuerpo expone verbos y espera a que alguien los llame. El backend manda
intención; el firmware la aplica sin dejar de mantener la cara viva.

```
GET /                       ayuda en texto plano
GET /status                 estado actual (emoción + química) en JSON
GET /face?preset=alegria    fija la química de una emoción
GET /face?s=0.7&n=0.3&d=0.6 química absoluta (parcial: los que falten se quedan)
GET /face?ds=0.1&dd=0.2     empujón relativo
GET /face?tag=[laughs]      etiqueta de voz (mueve la química)
GET /face?mouth=0.63        boca por voz (envolvente RMS 0..1)
GET /look?x=-0.5&y=0.2      dirige la mirada (-1..1); decae sola al centro
GET /wave                   saludo
```

Presets: `reposo alegria interes sorpresa miedo enojo desagrado angustia
verguenza`. La boca tiene watchdog: si el stream de `mouth` muere, cierra sola
a los 400 ms.

## Ruta

- [x] Motor facial paramétrico + capas de vida (simulador)
- [x] Port a ESP32 + SH1106 (U8g2)
- [x] Verbos HTTP: `/face`, `/wave`, `/look`
- [~] Backend (`backend/`): Whisper → Claude → ElevenLabs → RMS a la boca, +
      visión con reconocimiento facial. Panel de control web (`run.bat`).
- [ ] MQTT + Home Assistant
- [ ] Servos: PCA9685 + 4 GDL de cuello
- [ ] DOA del ReSpeaker → voltear hacia quien habla
