from unittest.mock import Mock, patch

import pytest

import bandeja


def _post(status=201):
    return patch.object(bandeja.requests, "post", return_value=Mock(status_code=status))


def test_apuntar_crea_issue_en_el_repo_con_el_token():
    with _post() as post:
        bandeja.apuntar("revisa la web", "tk", "yo/buzon")
    url = post.call_args.args[0]
    kwargs = post.call_args.kwargs
    assert url == "https://api.github.com/repos/yo/buzon/issues"
    assert kwargs["json"] == {"title": "revisa la web", "body": "revisa la web"}
    assert kwargs["headers"]["Authorization"] == "Bearer tk"
    assert kwargs["timeout"] == bandeja.TIMEOUT_SECONDS


def test_apuntar_recorta_titulo_largo():
    with _post() as post:
        bandeja.apuntar("x" * 300, "tk", "yo/buzon")
    assert len(post.call_args.kwargs["json"]["title"]) == bandeja.MAX_TITLE


def test_apuntar_sin_token_falla_sin_llamar():
    with _post() as post, pytest.raises(bandeja.BandejaError):
        bandeja.apuntar("hola", "", "yo/buzon")
    post.assert_not_called()


def test_apuntar_con_error_de_github_falla():
    with _post(401), pytest.raises(bandeja.BandejaError):
        bandeja.apuntar("hola", "tk", "yo/buzon")
