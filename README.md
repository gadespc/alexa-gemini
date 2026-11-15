# Alexa con Gemini

Skill de Alexa (es-ES) que responde con Google Gemini. Adaptación de
[WandLZhang/alexa-skill-gemini](https://github.com/WandLZhang/alexa-skill-gemini) (Apache-2.0):
español, historial por sesión (el original lo compartía entre usuarios), modelo Flash para no pasar
del límite de 8 s de Alexa, clave en cabecera y respuestas limpias para voz.

Uso: «Alexa, abre modo gemini» y preguntar. «Para» para salir.

## Instalar

1. Clave en <https://aistudio.google.com/apikey>.
2. <https://developer.amazon.com/alexa/console/ask> → *Create Skill* → nombre «Modo Gemini»,
   idioma *Spanish (ES)* → *Other* → *Custom* → *Alexa-hosted (Python)* → región *EU (Ireland)* →
   *Import skill* → `https://github.com/gadespc/alexa-gemini.git`.
3. *Build Skill*. Pestaña *Code* → en `lambda/` crear `.env` con `GOOGLE_API_KEY=<clave>` → *Save* → *Deploy*.
4. Pestaña *Test* → *Development*. Funciona en todos los Echo de la cuenta.

Variables opcionales en `.env`: `GEMINI_MODEL` (por defecto `gemini-3.5-flash`), `GEMINI_SEARCH=0` (sin búsqueda en Google) y `GEMINI_THINKING`
(`low`; vacío para no enviarlo).

## Desarrollo

```bash
python3 -m venv .venv && .venv/bin/pip install -r lambda/requirements.txt pytest ruff
.venv/bin/ruff check . && .venv/bin/pytest
```
