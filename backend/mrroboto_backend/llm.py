"""
El cerebro: Claude (Anthropic). Conversacion con memoria corta, streaming (por
si la respuesta se alarga) y persona configurable.

Modelo por defecto: claude-haiku-4-5 (rapido y barato, ideal para voz en tiempo
real). El panel permite cambiar a claude-sonnet-5 o claude-opus-5 para comparar.
"""

from __future__ import annotations

MODELS = {
    "claude-haiku-4-5": "Haiku 4.5 - rapido y economico (recomendado para voz)",
    "claude-sonnet-5": "Sonnet 5 - equilibrio calidad/costo",
    "claude-opus-5": "Opus 5 - maxima calidad (mas caro y lento)",
}


def verify_key(api_key: str) -> tuple[bool, str]:
    """Prueba minima contra la API. Devuelve (ok, mensaje)."""
    if not api_key:
        return False, "No hay API key."
    try:
        import anthropic
    except ImportError:
        return False, "Falta el paquete 'anthropic' (instala dependencias)."
    try:
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True, "Key de Anthropic valida."
    except anthropic.AuthenticationError:
        return False, "Key de Anthropic invalida (autenticacion)."
    except anthropic.PermissionDeniedError:
        return False, "La key no tiene permisos suficientes."
    except Exception as e:  # noqa: BLE001 - reporta cualquier fallo al panel
        return False, f"Error verificando Anthropic: {e}"


class Brain:
    """Mantiene la conversacion y llama a Claude."""

    def __init__(self, api_key: str, model: str, persona: str,
                 max_tokens: int = 400, history_turns: int = 12):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.persona = persona
        self.max_tokens = max_tokens
        self.history_turns = history_turns
        self.messages: list[dict] = []

    def reset(self) -> None:
        self.messages = []

    def _trim(self) -> None:
        # conserva los ultimos N turnos (user+assistant = 2 por turno)
        keep = self.history_turns * 2
        if len(self.messages) > keep:
            self.messages = self.messages[-keep:]

    def reply(self, user_text: str, on_delta=None) -> str:
        """
        Anade el turno del usuario, llama a Claude en streaming y devuelve el
        texto completo. 'on_delta' (opcional) recibe fragmentos segun llegan.
        """
        self.messages.append({"role": "user", "content": user_text})
        self._trim()

        text = ""
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.persona,
            messages=self.messages,
        ) as stream:
            for chunk in stream.text_stream:
                text += chunk
                if on_delta:
                    on_delta(chunk)

        text = text.strip()
        self.messages.append({"role": "assistant", "content": text})
        return text
