from unittest.mock import patch

import gemini
import lambda_function


def _evento(request, atributos=None):
    return {
        "version": "1.0",
        "session": {"new": False, "sessionId": "s", "application": {"applicationId": "a"},
                    "attributes": atributos or {}, "user": {"userId": "u"}},
        "context": {"System": {"application": {"applicationId": "a"}, "user": {"userId": "u"},
                               "device": {"deviceId": "d", "supportedInterfaces": {}}}},
        "request": dict({"requestId": "r", "timestamp": "2026-11-15T10:00:00Z", "locale": "es-ES"},
                        **request),
    }


def _intent(nombre, consulta=None):
    slots = {"query": {"name": "query", "value": consulta}} if consulta is not None else {}
    return {"type": "IntentRequest", "intent": {"name": nombre, "slots": slots}}


def _llamar(request, atributos=None):
    return lambda_function.lambda_handler(_evento(request, atributos), None)


def _voz(salida):
    return salida["response"]["outputSpeech"]["ssml"]


def test_launch_saluda_sin_llamar_a_gemini():
    with patch.object(gemini, "ask") as ask:
        salida = _llamar({"type": "LaunchRequest"})
    ask.assert_not_called()
    assert "pregunta" in _voz(salida).lower()
    assert salida["response"]["shouldEndSession"] is False


def test_chat_responde_y_guarda_historial_en_la_sesion():
    previo = [{"role": "user", "parts": [{"text": "a"}]}]
    nuevo = previo + [{"role": "user", "parts": [{"text": "b"}]}, {"role": "model", "parts": [{"text": "c"}]}]
    with patch.object(gemini, "ask", return_value=("**Hola** & adiós", nuevo)) as ask:
        salida = _llamar(_intent("ChatIntent", "b"), {"history": previo})
    assert ask.call_args.args[:2] == ("b", previo)
    assert "Hola &amp; adiós" in _voz(salida)
    assert salida["sessionAttributes"]["history"] == nuevo


def test_chat_recorta_historial_largo():
    largo = [{"role": "user", "parts": [{"text": str(i)}]} for i in range(50)]
    with patch.object(gemini, "ask", return_value=("ok", largo)):
        salida = _llamar(_intent("ChatIntent", "x"))
    assert len(salida["sessionAttributes"]["history"]) == lambda_function.MAX_HISTORY


def test_chat_con_error_de_gemini_avisa_y_sigue_escuchando():
    with patch.object(gemini, "ask", side_effect=gemini.GeminiError("x")):
        salida = _llamar(_intent("ChatIntent", "hola"))
    assert "no he podido" in _voz(salida).lower()
    assert salida["response"]["shouldEndSession"] is False


def test_chat_sin_consulta_pide_repetir():
    with patch.object(gemini, "ask") as ask:
        salida = _llamar(_intent("ChatIntent"))
    ask.assert_not_called()
    assert "no te he entendido" in _voz(salida).lower()


def test_fallback_pide_repetir():
    salida = _llamar(_intent("AMAZON.FallbackIntent"))
    assert "no te he entendido" in _voz(salida).lower()


def test_parar_se_despide_y_cierra():
    salida = _llamar(_intent("AMAZON.StopIntent"))
    assert "hasta luego" in _voz(salida).lower()
    assert salida["response"].get("shouldEndSession", True) is True


def test_ayuda_explica_uso():
    salida = _llamar(_intent("AMAZON.HelpIntent"))
    assert "pregunta" in _voz(salida).lower()
