from unittest.mock import Mock

import pytest

import gemini


def _respuesta(texto, status=200):
    r = Mock()
    r.status_code = status
    r.json.return_value = {"candidates": [{"content": {"parts": [{"text": texto}]}}]}
    return r


def test_payload_incluye_historial_pregunta_e_instrucciones():
    historial = [{"role": "user", "parts": [{"text": "hola"}]}]
    p = gemini.build_payload(historial, "¿qué hora es?", "breve", "low")
    assert p["contents"][-1] == {"role": "user", "parts": [{"text": "¿qué hora es?"}]}
    assert p["contents"][0]["parts"][0]["text"] == "hola"
    assert p["systemInstruction"]["parts"][0]["text"] == "breve"
    assert p["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_payload_sin_nivel_de_razonamiento_omite_thinking():
    p = gemini.build_payload([], "hola", "breve", "")
    assert "thinkingConfig" not in p["generationConfig"]


def test_payload_no_modifica_el_historial_original():
    historial = []
    gemini.build_payload(historial, "hola", "breve", "")
    assert historial == []


def test_extract_text_une_partes_e_ignora_razonamiento():
    data = {"candidates": [{"content": {"parts": [
        {"text": "pensando", "thought": True}, {"text": "Hola "}, {"text": "mundo"}]}}]}
    assert gemini.extract_text(data) == "Hola mundo"


@pytest.mark.parametrize("data", [{}, {"candidates": []}, {"candidates": [{}]}])
def test_extract_text_sin_contenido_devuelve_vacio(data):
    assert gemini.extract_text(data) == ""


def test_clean_for_speech_quita_markdown_y_escapa_ssml():
    texto = "## Título\n**Negrita** y `código` & <x>\n- punto"
    assert gemini.clean_for_speech(texto) == "Título Negrita y código &amp; &lt;x&gt; punto"


def test_trim_history_conserva_los_ultimos_mensajes():
    h = [{"role": "user", "parts": [{"text": str(i)}]} for i in range(10)]
    assert gemini.trim_history(h, 4) == h[-4:]


def test_ask_devuelve_respuesta_y_amplia_historial():
    http = Mock()
    http.post.return_value = _respuesta("Son las tres")
    texto, historial = gemini.ask("¿hora?", [], "clave", "modelo-x", http=http)
    assert texto == "Son las tres"
    assert [m["role"] for m in historial] == ["user", "model"]
    args, kwargs = http.post.call_args
    assert "models/modelo-x:generateContent" in args[0]
    assert "clave" not in args[0]
    assert kwargs["headers"]["x-goog-api-key"] == "clave"
    assert kwargs["timeout"] == gemini.TIMEOUT_SECONDS


def test_ask_con_error_http_lanza_gemini_error():
    http = Mock()
    http.post.return_value = _respuesta("", status=429)
    with pytest.raises(gemini.GeminiError):
        gemini.ask("hola", [], "clave", "m", http=http)


def test_ask_con_respuesta_vacia_lanza_gemini_error():
    http = Mock()
    http.post.return_value = _respuesta("")
    with pytest.raises(gemini.GeminiError):
        gemini.ask("hola", [], "clave", "m", http=http)


def test_ask_sin_clave_lanza_gemini_error():
    with pytest.raises(gemini.GeminiError):
        gemini.ask("hola", [], "", "m", http=Mock())


def test_payload_activa_busqueda_en_google_si_se_pide():
    assert gemini.build_payload([], "hola", "s", "", search=True)["tools"] == [{"google_search": {}}]
    assert "tools" not in gemini.build_payload([], "hola", "s", "")


def test_payload_deja_margen_de_tokens_para_el_razonamiento():
    assert gemini.build_payload([], "hola", "s", "low")["generationConfig"]["maxOutputTokens"] >= 2048


def test_extract_text_cortado_por_limite_termina_en_frase_completa():
    data = {"candidates": [{"finishReason": "MAX_TOKENS",
                            "content": {"parts": [{"text": "Empezó en 1939. Terminó en 1945 con la rendi"}]}}]}
    assert gemini.extract_text(data) == "Empezó en 1939."


def test_extract_text_cortado_sin_frase_completa_lo_devuelve_tal_cual():
    data = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "Empezó en"}]}}]}
    assert gemini.extract_text(data) == "Empezó en"


def test_ask_envia_busqueda_cuando_se_activa():
    http = Mock()
    http.post.return_value = _respuesta("ok")
    gemini.ask("hola", [], "clave", "m", search=True, http=http)
    assert http.post.call_args.kwargs["json"]["tools"] == [{"google_search": {}}]
