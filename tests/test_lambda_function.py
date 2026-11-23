from unittest.mock import patch

import pytest

import bandeja
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


def test_instrucciones_piden_brevedad_datos_reales_y_fecha_de_hoy():
    texto = lambda_function.system_prompt(lambda_function.date(2026, 11, 15))
    assert "15/11/2026" in texto
    assert "40 palabras" in texto


def test_chat_usa_busqueda_por_defecto(monkeypatch):
    monkeypatch.delenv("GEMINI_SEARCH", raising=False)
    with patch.object(gemini, "ask", return_value=("ok", [])) as ask:
        _llamar(_intent("ChatIntent", "x"))
    assert ask.call_args.kwargs["search"] is True


def test_chat_sin_busqueda_si_se_desactiva(monkeypatch):
    monkeypatch.setenv("GEMINI_SEARCH", "0")
    with patch.object(gemini, "ask", return_value=("ok", [])) as ask:
        _llamar(_intent("ChatIntent", "x"))
    assert ask.call_args.kwargs["search"] is False


def _apuntar(nota=None):
    slots = {"nota": {"name": "nota", "value": nota}} if nota is not None else {}
    return {"type": "IntentRequest", "intent": {"name": "ApuntarIntent", "slots": slots}}


def test_apuntar_pide_confirmacion_sin_escribir():
    with patch.object(bandeja, "apuntar") as apuntar:
        salida = _llamar(_apuntar("revisa la web"))
    apuntar.assert_not_called()
    assert "revisa la web" in _voz(salida)
    assert "¿lo escribo?" in _voz(salida).lower()
    assert salida["sessionAttributes"]["nota"] == "revisa la web"
    assert salida["response"]["shouldEndSession"] is False


def test_apuntar_sin_nota_pregunta_que_apuntar():
    salida = _llamar(_apuntar())
    assert "qué apunto" in _voz(salida).lower()
    assert "nota" not in salida.get("sessionAttributes", {})


def test_si_escribe_la_nota_pendiente(monkeypatch):
    monkeypatch.setenv("BANDEJA_GITHUB_TOKEN", "tk")
    monkeypatch.delenv("BANDEJA_REPO", raising=False)
    with patch.object(bandeja, "apuntar") as apuntar:
        salida = _llamar(_intent("AMAZON.YesIntent"), {"nota": "revisa la web"})
    apuntar.assert_called_once_with("revisa la web", "tk", "gadespc/bandeja-alexa")
    assert "apuntado" in _voz(salida).lower()
    assert "nota" not in salida["sessionAttributes"]


def test_si_con_error_avisa_y_no_guarda_la_nota():
    with patch.object(bandeja, "apuntar", side_effect=bandeja.BandejaError("x")):
        salida = _llamar(_intent("AMAZON.YesIntent"), {"nota": "a"})
    assert "no he podido apuntarlo" in _voz(salida).lower()
    assert "nota" not in salida["sessionAttributes"]


def test_si_sin_nota_pendiente_no_escribe():
    with patch.object(bandeja, "apuntar") as apuntar:
        salida = _llamar(_intent("AMAZON.YesIntent"))
    apuntar.assert_not_called()
    assert "nada pendiente" in _voz(salida).lower()


def test_no_descarta_la_nota():
    with patch.object(bandeja, "apuntar") as apuntar:
        salida = _llamar(_intent("AMAZON.NoIntent"), {"nota": "a"})
    apuntar.assert_not_called()
    assert "no lo apunto" in _voz(salida).lower()
    assert "nota" not in salida["sessionAttributes"]


@pytest.mark.parametrize("respuesta", ["sí", "Sí.", "vale", "escríbelo"])
def test_si_dicho_como_pregunta_tambien_confirma(respuesta):
    with patch.object(bandeja, "apuntar") as apuntar, patch.object(gemini, "ask") as ask:
        _llamar(_intent("ChatIntent", respuesta), {"nota": "a"})
    apuntar.assert_called_once()
    ask.assert_not_called()


def test_otra_pregunta_con_nota_pendiente_la_descarta_y_responde():
    with patch.object(bandeja, "apuntar") as apuntar, patch.object(gemini, "ask", return_value=("ok", [])):
        salida = _llamar(_intent("ChatIntent", "qué hora es"), {"nota": "a"})
    apuntar.assert_not_called()
    assert "nota" not in salida["sessionAttributes"]


@pytest.mark.parametrize("frase, nota", [
    ("revisa las copias de seguridad y apúntalo en la bandeja de obsidian", "revisa las copias de seguridad"),
    ("hazme un presupuesto para Ana y apúntalo", "hazme un presupuesto para Ana"),
    ("apúntalo en la bandeja: llamar al gestor", "llamar al gestor"),
    ("dile a claude que mire la web", "que mire la web"),
    ("cambia el logo, anótalo para Claude", "cambia el logo"),
    ("guarda en obsidian comprar discos duros", "comprar discos duros"),
])
def test_pedir_apuntar_en_una_frase_normal_pide_confirmacion(frase, nota):
    with patch.object(bandeja, "apuntar") as apuntar, patch.object(gemini, "ask") as ask:
        salida = _llamar(_intent("ChatIntent", frase))
    apuntar.assert_not_called()
    ask.assert_not_called()
    assert salida["sessionAttributes"]["nota"] == nota
    assert "¿lo escribo?" in _voz(salida).lower()


@pytest.mark.parametrize("frase", ["qué es obsidian", "quién es claude monet", "cómo se apunta uno al paro"])
def test_preguntas_normales_no_se_apuntan(frase):
    with patch.object(gemini, "ask", return_value=("ok", [])) as ask:
        salida = _llamar(_intent("ChatIntent", frase))
    ask.assert_called_once()
    assert "nota" not in salida["sessionAttributes"]


def test_pedir_apuntar_sin_contenido_pregunta_que_apuntar():
    salida = _llamar(_intent("ChatIntent", "apúntalo en la bandeja"))
    assert "qué apunto" in _voz(salida).lower()
