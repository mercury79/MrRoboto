"""
Los ojos: camara (Logitech C920) -> detectar cara -> reconocer si eres tu.

Todo con OpenCV puro (wheels, sin compilador): detector Haar + reconocedor LBPH.
Te "enrolas" una vez (capturamos ~30 fotos de tu cara), y a partir de ahi el
backend te reconoce y hace que MrRoboto reaccione (te mira, saluda, se pone
contento). Las fotos y el modelo se quedan en config/faces/ (gitignored).

LBPH es sencillo y offline; suficiente para "eres tu vs. un desconocido" en luz
estable. Se puede subir a un modelo mejor (insightface) mas adelante.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import FACES_DIR

_MODEL_PATH = FACES_DIR / "lbph.yml"
_LABELS_PATH = FACES_DIR / "labels.json"
_CROP = 200  # tamano normalizado de la cara en gris


def open_camera(index: int):
    import cv2
    # CAP_DSHOW arranca mas rapido y estable en Windows con la C920.
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    return cap


class FaceRecognizer:
    def __init__(self):
        import cv2
        self.cv2 = cv2
        self.cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.labels: dict[int, str] = {}
        self.trained = False
        self._load()

    # --- persistencia ---------------------------------------------------

    def _load(self) -> None:
        if _MODEL_PATH.exists() and _LABELS_PATH.exists():
            try:
                self.recognizer.read(str(_MODEL_PATH))
                self.labels = {int(k): v for k, v in
                               json.loads(_LABELS_PATH.read_text(encoding="utf-8")).items()}
                self.trained = True
            except Exception:  # noqa: BLE001
                self.trained = False

    def enrolled(self) -> list[str]:
        return sorted(set(self.labels.values()))

    # --- deteccion ------------------------------------------------------

    def detect(self, gray):
        return self.cascade.detectMultiScale(gray, scaleFactor=1.2,
                                              minNeighbors=5, minSize=(80, 80))

    def _crop(self, gray, rect):
        x, y, w, h = rect
        face = gray[y:y + h, x:x + w]
        face = self.cv2.resize(face, (_CROP, _CROP))
        return self.cv2.equalizeHist(face)

    @staticmethod
    def largest(rects):
        if len(rects) == 0:
            return None
        return max(rects, key=lambda r: r[2] * r[3])

    # --- reconocimiento -------------------------------------------------

    def recognize(self, gray, rect):
        """Devuelve (nombre|None, distancia). Menor distancia = mas seguro."""
        if not self.trained:
            return None, 999.0
        label, dist = self.recognizer.predict(self._crop(gray, rect))
        return self.labels.get(label), float(dist)

    # --- enrolamiento ---------------------------------------------------

    def enroll_from_camera(self, name: str, camera_index: int,
                           samples: int = 30, on_progress=None) -> dict:
        """Captura fotos de la cara mas grande y reentrena con todo el dataset."""
        cv2 = self.cv2
        name = name.strip()
        if not name:
            return {"ok": False, "error": "Falta el nombre."}

        person_dir = FACES_DIR / _safe(name)
        person_dir.mkdir(parents=True, exist_ok=True)

        cap = open_camera(camera_index)
        if not cap.isOpened():
            return {"ok": False, "error": f"No pude abrir la camara {camera_index}."}

        captured = 0
        tries = 0
        try:
            while captured < samples and tries < samples * 12:
                tries += 1
                ok, frame = cap.read()
                if not ok:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rect = self.largest(self.detect(gray))
                if rect is None:
                    continue
                crop = self._crop(gray, rect)
                cv2.imwrite(str(person_dir / f"{captured:03d}.png"), crop)
                captured += 1
                if on_progress:
                    on_progress(captured, samples)
        finally:
            cap.release()

        if captured < 5:
            return {"ok": False, "error": f"Solo capture {captured} caras. Mejora la luz y encuadra tu rostro."}

        trained = self._retrain()
        return {"ok": True, "captured": captured, "people": trained}

    def _retrain(self) -> list[str]:
        """Reentrena LBPH desde todas las carpetas de config/faces/."""
        import numpy as np
        cv2 = self.cv2
        images, ids = [], []
        names = sorted([d.name for d in FACES_DIR.iterdir() if d.is_dir()])
        self.labels = {}
        for label_id, folder in enumerate(names):
            self.labels[label_id] = folder
            for img_path in (FACES_DIR / folder).glob("*.png"):
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                images.append(img)
                ids.append(label_id)

        if not images:
            self.trained = False
            return []

        self.recognizer.train(images, np.array(ids))
        self.recognizer.write(str(_MODEL_PATH))
        _LABELS_PATH.write_text(json.dumps(self.labels, ensure_ascii=False), encoding="utf-8")
        self.trained = True
        return [self.labels[i] for i in sorted(self.labels)]


def _safe(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in " _-").strip() or "persona"
