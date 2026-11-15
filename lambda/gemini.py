"""Cliente mínimo de la API de Gemini pensado para respuestas habladas."""
import re

import requests

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Alexa corta a los 8 s: dejamos margen para responder.
TIMEOUT_SECONDS = 6.5
# Incluye los tokens de razonamiento: con poco margen la respuesta se corta.
MAX_OUTPUT_TOKENS = 2048

_MARKDOWN = re.compile(r"[*_`#]+|^\s*(?:[-•>]|\d+\.)\s+", re.MULTILINE)
_SPACES = re.compile(r"\s+")
_LAST_SENTENCE = re.compile(r"^(.*[.!?])\s", re.DOTALL)


class GeminiError(Exception):
    """Gemini no devolvió una respuesta utilizable."""


def _message(role, text):
    return {"role": role, "parts": [{"text": text}]}


def build_payload(history, question, system, thinking_level, search=False):
    config = {"maxOutputTokens": MAX_OUTPUT_TOKENS}
    if thinking_level:
        config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": list(history) + [_message("user", question)],
        "generationConfig": config,
    }
    if search:
        payload["tools"] = [{"google_search": {}}]
    return payload


def extract_text(data):
    candidates = data.get("candidates") or [{}]
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if candidates[0].get("finishReason") == "MAX_TOKENS":
        complete = _LAST_SENTENCE.match(text + " ")
        text = complete.group(1) if complete else text
    return text


def clean_for_speech(text):
    text = _MARKDOWN.sub(" ", text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _SPACES.sub(" ", text).strip()


def trim_history(history, max_messages):
    return history[-max_messages:]


def ask(question, history, api_key, model, system="", thinking_level="", search=False, http=requests):
    """Devuelve (respuesta, historial ampliado) o lanza GeminiError."""
    if not api_key:
        raise GeminiError("Falta GOOGLE_API_KEY")
    def post(with_search):
        return http.post(
            API_URL.format(model=model),
            json=build_payload(history, question, system, thinking_level, with_search),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            timeout=TIMEOUT_SECONDS,
        )

    response = post(search)
    if search and response.status_code == 429:
        # Sin cupo de búsqueda en Google: mejor responder sin ella que fallar.
        response = post(False)
    if response.status_code != 200:
        raise GeminiError(f"HTTP {response.status_code}")
    text = extract_text(response.json())
    if not text:
        raise GeminiError("Respuesta vacía")
    return text, list(history) + [_message("user", question), _message("model", text)]
