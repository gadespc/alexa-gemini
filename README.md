# Alexa con Gemini

Skill de Alexa (es-ES) que responde con Google Gemini. Adaptación de
[WandLZhang/alexa-skill-gemini](https://github.com/WandLZhang/alexa-skill-gemini) (Apache-2.0):
español, historial por sesión (el original lo compartía entre usuarios), modelo Flash para no pasar
del límite de 8 s de Alexa, clave en cabecera y respuestas limpias para voz.

Uso: «Alexa, abre modo genio» y preguntar (el Echo transcribe «Gemini» unas veces como «gemini» y otras como «géminis»: por eso la invocación evita esa palabra). Límites de voz: Alexa deja de escuchar tras ~1 s de pausa y unos 8 s de frase, y la respuesta debe llegar en 8 s. «Para» para salir.

Notas para Claude: «apunta …», «dile a Claude …» o en una frase normal («… y apúntalo en la bandeja»). Alexa la repite y pregunta «¿Lo escribo?»; solo con «sí» la
deja como issue en el repo privado `BANDEJA_REPO`. En el PC, `claude-bandeja` la pasa a «Para Claude.md» → Pendiente
y cierra el issue.

## Instalar

1. Clave en <https://aistudio.google.com/apikey>.
2. <https://developer.amazon.com/alexa/console/ask> → *Create Skill* → nombre «Modo Gemini»,
   idioma *Spanish (ES)* → *Other* → *Custom* → *Alexa-hosted (Python)* → región *EU (Ireland)* →
   *Import skill* → `https://github.com/gadespc/alexa-gemini.git`.
3. *Build Skill*. Pestaña *Code* → en `lambda/` crear `.env` con `GOOGLE_API_KEY=<clave>` → *Save* → *Deploy*.
4. Pestaña *Test* → *Development*. Funciona en todos los Echo de la cuenta.

Variables opcionales en `.env`: `GEMINI_MODEL` (por defecto `gemini-3.5-flash`), `GEMINI_SEARCH=0` (sin búsqueda en Google) y `GEMINI_THINKING`
(`low`; vacío para no enviarlo). Para las notas: `BANDEJA_GITHUB_TOKEN` (token *fine-grained* con *Issues: Read and write* solo
en ese repo) y `BANDEJA_REPO` (por defecto `gadespc/bandeja-alexa`).

## Mantenimiento

- El código que corre es el del editor de la consola (pestaña *Code*); no se sincroniza con GitHub.
  Tras un cambio aquí: copiar `lambda/*.py` al editor → *Save* → *Deploy*. Si cambia `interactionModels/`, pegarlo en
  *Build* → *JSON Editor* → *Save* → *Build skill*.
- Errores: *Code* → *CloudWatch Logs*.
- Trampas conocidas: la importación deja la invocación en «change me» (*Build* → *Invocations* →
  «modo genio» → *Build skill*); el runtime es Python 3.8 y exige `urllib3` 1.x; la búsqueda en
  Google da 429 sin facturación en AI Studio y la skill responde entonces sin ella.

## Desarrollo

```bash
python3 -m venv .venv && .venv/bin/pip install -r lambda/requirements.txt pytest ruff
.venv/bin/ruff check . && .venv/bin/pytest
```
