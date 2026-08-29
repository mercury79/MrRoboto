"""
Cliente del cuerpo (ESP32). Traduce intencion del backend a los verbos HTTP
del paso 4. Si el robot esta deshabilitado o no responde, no revienta: la
conversacion sigue aunque no haya cara.
"""

from __future__ import annotations

import httpx


class Robot:
    def __init__(self, ip: str, enabled: bool = True, timeout_s: float = 3.0):
        self.ip = ip
        self.enabled = enabled
        self.timeout_s = timeout_s

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        if not self.enabled:
            return None
        url = f"http://{self.ip}{path}"
        try:
            r = httpx.get(url, params=params, timeout=self.timeout_s)
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                return {"raw": r.text}
        except (httpx.HTTPError, OSError):
            return None

    # --- verbos ---------------------------------------------------------

    def status(self) -> dict | None:
        return self._get("/status")

    def preset(self, name: str) -> dict | None:
        return self._get("/face", {"preset": name})

    def chem(self, s: float | None = None, n: float | None = None, d: float | None = None) -> dict | None:
        params = {}
        if s is not None:
            params["s"] = round(float(s), 3)
        if n is not None:
            params["n"] = round(float(n), 3)
        if d is not None:
            params["d"] = round(float(d), 3)
        return self._get("/face", params)

    def nudge(self, ds: float = 0.0, dn: float = 0.0, dd: float = 0.0) -> dict | None:
        return self._get("/face", {"ds": round(ds, 3), "dn": round(dn, 3), "dd": round(dd, 3)})

    def voice_tag(self, tag: str) -> dict | None:
        # el firmware espera [laughs] etc. tal cual
        return self._get("/face", {"tag": tag})

    def mouth(self, level: float) -> dict | None:
        return self._get("/face", {"mouth": round(max(0.0, min(1.0, level)), 3)})

    def look(self, x: float = 0.0, y: float = 0.0) -> dict | None:
        return self._get("/look", {"x": round(x, 3), "y": round(y, 3)})

    def wave(self) -> dict | None:
        return self._get("/wave")

    def reachable(self) -> bool:
        return self.status() is not None


# Etiquetas de voz que el firmware entiende (deben coincidir con VOICE_TAGS del
# ESP32). El agente las escribe en su texto; aqui las detectamos para: (a)
# mandarlas al robot y (b) quitarlas del texto que se manda a la voz si el TTS
# no las soporta.
VOICE_TAGS = [
    "[laughs]", "[chuckles]", "[sighs]", "[gasps]",
    "[whispers]", "[excited]", "[sad]", "[angry]", "[curious]",
]
