// Verbos HTTP del cuerpo (paso 4).
//
// El backend manda INTENCION por HTTP; el firmware la aplica sin dejar de
// mantener la cara viva. El cuerpo no decide nada: expone verbos y espera a
// que alguien los llame.
//
//   GET /            ayuda en texto plano
//   GET /status      estado actual (emocion + quimica) en JSON
//   GET /face        fija intencion. Parametros (todos opcionales):
//                      preset=alegria|reposo|...   fija la quimica de una emocion
//                      s= n= d=   (0..1)            quimica absoluta (parcial ok)
//                      ds= dn= dd=                  empujon relativo
//                      tag=[laughs]                 etiqueta de voz
//                      mouth=0.63 (0..1)            envolvente RMS de la boca
//   GET /look?x=&y=  dirige la mirada (-1..1); decae sola al centro
//   GET /wave        saludo (chispa de entusiasmo + mirada al frente)
//
// Todas responden el estado resultante en JSON.

#pragma once

class FaceEngine;

// Registra las rutas y arranca el servidor en el puerto 80. Llamar una vez,
// despues de tener WiFi.
void httpSetup(FaceEngine* engine);

// Atiende clientes pendientes. Llamar en cada vuelta del loop.
void httpLoop();
