"""Apunta notas dictadas para la bandeja de Claude: issues de un repo privado de GitHub."""
import requests

API_URL = "https://api.github.com/repos/{repo}/issues"
TIMEOUT_SECONDS = 5
MAX_TITLE = 120


class BandejaError(Exception):
    """No se pudo apuntar la nota."""


def apuntar(texto, token, repo):
    if not token:
        raise BandejaError("Falta BANDEJA_GITHUB_TOKEN")
    respuesta = requests.post(
        API_URL.format(repo=repo),
        json={"title": texto[:MAX_TITLE], "body": texto},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=TIMEOUT_SECONDS,
    )
    if respuesta.status_code != 201:
        raise BandejaError(f"GitHub respondió {respuesta.status_code}")
