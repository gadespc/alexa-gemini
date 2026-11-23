"""Skill de Alexa que responde con Google Gemini, en español."""
import logging
import os
import re
from datetime import date

import ask_sdk_core.utils as ask_utils
import requests
from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from dotenv import load_dotenv

import bandeja
import gemini

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_HISTORY = 12
SYSTEM_PROMPT = (
    "Asistente de voz Alexa. Hoy es {hoy}. Responde en español, máximo 40 palabras, directo al dato "
    "clave y real. Si no lo sabes, dilo. Sin listas ni markdown."
)


def system_prompt(today):
    return SYSTEM_PROMPT.format(hoy=today.strftime("%d/%m/%Y"))
REPROMPT = "¿Algo más?"
NOT_UNDERSTOOD = "Perdona, no te he entendido. ¿Puedes repetirlo?"
CONFIRM = "¿Lo escribo? Di sí o no."
YES_WORDS = {"sí", "si", "vale", "escríbelo", "apúntalo", "confirmo"}
NO_WORDS = {"no", "cancela", "déjalo"}
_VERB = r"(?:ap[uú]nt|an[oó]t|gu[aá]rd|escr[ií]b|m[aá]nd|p[aá]s)\w*|dile"
_DEST = r"(?:bandeja|obsidian|claude)(?:\s+de\s+(?:obsidian|claude))?"
NOTE_REQUESTS = (
    re.compile(rf"\b(?:y\s+)?(?:{_VERB})\s+(?:(?:lo|la|en|a|para|al)\s+)*{_DEST}\b", re.IGNORECASE),
    re.compile(r"\b(?:y\s+)?(?:ap[uú]nt|an[oó]t)[aá]\s?l[oa]\b", re.IGNORECASE),
)


def _settings():
    return {
        "api_key": os.getenv("GOOGLE_API_KEY", ""),
        "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        "thinking_level": os.getenv("GEMINI_THINKING", "low"),
        "search": os.getenv("GEMINI_SEARCH", "1") != "0",
        "bandeja_token": os.getenv("BANDEJA_GITHUB_TOKEN", ""),
        "bandeja_repo": os.getenv("BANDEJA_REPO", "gadespc/bandeja-alexa"),
    }


def _listen(handler_input, speech, reprompt=REPROMPT):
    return handler_input.response_builder.speak(speech).ask(reprompt).response


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        return _listen(handler_input, "Hola, soy Gemini. Hazme una pregunta.", "¿Qué quieres saber?")


def _session(handler_input):
    return handler_input.attributes_manager.session_attributes


def _confirm_note(handler_input):
    note = _session(handler_input).pop("nota", None)
    if not note:
        return _listen(handler_input, "No tengo nada pendiente de apuntar.")
    settings = _settings()
    try:
        bandeja.apuntar(note, settings["bandeja_token"], settings["bandeja_repo"])
    except (bandeja.BandejaError, requests.RequestException):
        logger.exception("Fallo al apuntar en la bandeja")
        return _listen(handler_input, "Lo siento, no he podido apuntarlo. Prueba más tarde.")
    return _listen(handler_input, "Apuntado. Claude lo verá en unos minutos.")


def _discard_note(handler_input):
    if _session(handler_input).pop("nota", None):
        return _listen(handler_input, "Vale, no lo apunto.")
    return _listen(handler_input, REPROMPT)


def extract_note(text):
    """Nota pedida en una frase normal («… y apúntalo en la bandeja»); None si no pide apuntar."""
    for pattern in NOTE_REQUESTS:
        match = pattern.search(text)
        if match:
            rest = f"{text[:match.start()]} {text[match.end():]}"
            return " ".join(rest.split()).strip(" ,.:;")
    return None


def _ask_to_confirm(handler_input, note):
    if not note:
        return _listen(handler_input, "¿Qué apunto para Claude? Di apunta y la nota.")
    _session(handler_input)["nota"] = note
    return _listen(handler_input, f"Voy a apuntar para Claude: {note}. {CONFIRM}", CONFIRM)


class ApuntarIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ApuntarIntent")(handler_input)

    def handle(self, handler_input):
        slot = ask_utils.get_slot(handler_input, "nota")
        return _ask_to_confirm(handler_input, slot.value if slot else None)


class YesIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.YesIntent")(handler_input)

    def handle(self, handler_input):
        return _confirm_note(handler_input)


class NoIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.NoIntent")(handler_input)

    def handle(self, handler_input):
        return _discard_note(handler_input)


class ChatIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ChatIntent")(handler_input)

    def handle(self, handler_input):
        slot = ask_utils.get_slot(handler_input, "query")
        question = slot.value if slot else None
        if not question:
            return _listen(handler_input, NOT_UNDERSTOOD)
        attributes = _session(handler_input)
        if "nota" in attributes:
            word = question.strip(" .¡!¿?").lower()
            if word in YES_WORDS:
                return _confirm_note(handler_input)
            del attributes["nota"]
            if word in NO_WORDS:
                return _listen(handler_input, "Vale, no lo apunto.")
        note = extract_note(question)
        if note is not None:
            return _ask_to_confirm(handler_input, note)
        settings = _settings()
        try:
            answer, history = gemini.ask(
                question, attributes.get("history", []), settings["api_key"], settings["model"],
                system=system_prompt(date.today()), thinking_level=settings["thinking_level"],
                search=settings["search"],
            )
        except (gemini.GeminiError, requests.RequestException, ValueError):
            logger.exception("Fallo al consultar Gemini")
            return _listen(handler_input, "Lo siento, no he podido obtener respuesta. Prueba otra vez.")
        attributes["history"] = gemini.trim_history(history, MAX_HISTORY)
        return _listen(handler_input, gemini.clean_for_speech(answer))


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        return _listen(handler_input, "Hazme cualquier pregunta y te respondo. Para dejarle una nota a Claude, di apunta y la nota. Para salir, di para.")


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        return _listen(handler_input, NOT_UNDERSTOOD)


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input)
                or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        return handler_input.response_builder.speak("Hasta luego.").set_should_end_session(True).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error("Error no controlado", exc_info=exception)
        return _listen(handler_input, "Lo siento, algo ha fallado. Prueba otra vez.")


sb = SkillBuilder()
for handler in (LaunchRequestHandler(), ApuntarIntentHandler(), YesIntentHandler(), NoIntentHandler(),
                ChatIntentHandler(), HelpIntentHandler(), FallbackIntentHandler(),
                CancelOrStopIntentHandler(), SessionEndedRequestHandler()):
    sb.add_request_handler(handler)
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
