# MrRoboto — Backend (Paso 5)

El **cerebro** de MrRoboto, en la PC. Le da oído, voz y ojos, y le manda
*intención* al cuerpo (ESP32) por los verbos HTTP del paso 4. El cuerpo sigue
siendo un periférico: si el backend no está, la cara sigue viva sola.

```
Micrófono ─▶ VAD ─▶ Whisper ─▶ Claude ─▶ ElevenLabs ─▶ (RMS) ─▶ /face?mouth=
Cámara    ─▶ detectar+reconocer ─▶ /wave · /look · /face?preset=
```

## Arrancar

1. Doble clic en **`run.bat`** (crea el entorno, instala el panel y abre
   `http://127.0.0.1:8080`).
2. En el panel: pega tus **API keys** (Anthropic obligatoria; ElevenLabs
   opcional), dale **Verificar** y **Guardar**. Se guardan en
   `config/secrets.json`, **local y fuera de git**.
3. Para voz + visión, corre **`install-full.bat`** una vez (Whisper, TTS,
   OpenCV). La primera transcripción descarga el modelo Whisper.
4. **Enrólate** (reconocimiento facial): escribe tu nombre y "Enrolar mi cara".
5. **▶ Iniciar** la conversación. Háblale (VAD: detecta cuándo hablas). Cuando
   te vea, te saluda por tu nombre.

## Opciones (todas se guardan permanentemente)

- **Cerebro**: modelo Claude — por defecto **Haiku 4.5** (rápido y económico,
  ideal para voz); puedes cambiar a Sonnet 5 u Opus 5 para comparar.
- **Oído**: modelo Whisper (`large-v3` = "Whisper 3"), idioma, sensibilidad VAD.
- **Voz**: **ElevenLabs** (natural, de pago) o **gratis/offline** (voz de
  Windows). Modelo y voz de ElevenLabs seleccionables.
- **Ojos**: índice de cámara (la C920 suele ser 0), reconocerte, saludo por voz.

## Privacidad

`config/settings.json`, `config/secrets.json` y `config/faces/` (tus fotos)
están en `.gitignore`. Nada sensible sube al repositorio. Las keys se guardan
en claro en tu máquina; el backend corre solo en `127.0.0.1`.

## Notas

- **VAD half-duplex**: mientras MrRoboto habla, el micrófono se pausa para no
  oírse a sí mismo.
- **Reconocimiento**: OpenCV LBPH (offline, sin compilador). Suficiente para
  "eres tú vs. desconocido" en luz estable; se puede subir a insightface luego.
- Es un primer corte funcional del Paso 5; iremos afinando naturalidad y
  latencia (streaming por frases, wake word, etc.).
