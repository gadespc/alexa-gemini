"""Skill de Alexa que responde con Google Gemini, en español."""
import logging
import os

import ask_sdk_core.utils as ask_utils
import requests
from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from dotenv import load_dotenv

import gemini

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_HISTORY = 12
SYSTEM_PROMPT = (
    "Eres un asistente de voz en un altavoz Alexa. Responde siempre en español de España, "
    "en 1 a 3 frases claras, sin listas, sin emojis y sin formato markdown. "
    "Si la pregunta es ambigua, da la respuesta más probable."
)
REPROMPT = "¿Algo más?"
NOT_UNDERSTOOD = "Perdona, no te he entendido. ¿Puedes repetirlo?"


def _settings():
    return {
        "api_key": os.getenv("GOOGLE_API_KEY", ""),
        "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        "thinking_level": os.getenv("GEMINI_THINKING", "low"),
    }


def _listen(handler_input, speech, reprompt=REPROMPT):
    return handler_input.response_builder.speak(speech).ask(reprompt).response


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        return _listen(handler_input, "Hola, soy Gemini. Hazme una pregunta.", "¿Qué quieres saber?")


class ChatIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ChatIntent")(handler_input)

    def handle(self, handler_input):
        slot = ask_utils.get_slot(handler_input, "query")
        question = slot.value if slot else None
        if not question:
            return _listen(handler_input, NOT_UNDERSTOOD)
        attributes = handler_input.attributes_manager.session_attributes
        settings = _settings()
        try:
            answer, history = gemini.ask(
                question, attributes.get("history", []), settings["api_key"], settings["model"],
                system=SYSTEM_PROMPT, thinking_level=settings["thinking_level"],
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
        return _listen(handler_input, "Hazme cualquier pregunta y te respondo. Para salir, di para.")


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
for handler in (LaunchRequestHandler(), ChatIntentHandler(), HelpIntentHandler(), FallbackIntentHandler(),
                CancelOrStopIntentHandler(), SessionEndedRequestHandler()):
    sb.add_request_handler(handler)
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
