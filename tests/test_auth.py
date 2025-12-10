import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from Api.main import app
from Api.routes.auth import detect_environment

client = TestClient(app)


# Teste conexão com a api
def test_detect_environment_localhost():
    request = type("Request", (), {"headers": {"host": "localhost:8000"}})
    redirect, frontend = detect_environment(request)
    assert "localhost" in redirect
    assert "localhost" in frontend


@pytest.mark.asyncio
@patch("Api.routes.auth.oauth.google.authorize_redirect", new_callable=AsyncMock)
async def test_login_redirect(mock_auth_redirect):
    mock_auth_redirect.return_value = {"url": "http://mock.redirect"}

    response = client.get("/auth/login", headers={"host": "localhost"})

    assert response.status_code == 200
    mock_auth_redirect.assert_called_once()


# Testa a autenticação do google(retorno certo)
@pytest.mark.asyncio
@patch("Api.routes.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
@patch("Api.routes.auth.setup_drive_structure")
async def test_callback_success(mock_drive_setup, mock_authorize):

    # Mock do Google
    mock_authorize.return_value = {
        "userinfo": {
            "email": "teste@gmail.com",
            "name": "Teste",
            "picture": "http://exemplo.jpg",
        },
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
    }

    # Mock das pastas
    mock_drive_setup.return_value = {
        "root": "root_id",
        "bd": "bd_id",
        "characters": "chars_id",
    }

    state_data = {"frontend": "http://localhost:4200/login-success"}
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

    # Desativar redirects no TestClient
    response = client.get(
        f"/auth/callback?state={encoded_state}",
        headers={"host": "localhost"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)

    redirect_url = response.headers.get("location", "")
    assert redirect_url.startswith("http://localhost:4200/login-success?token=")

    mock_authorize.assert_called_once()
    mock_drive_setup.assert_called_once()


# Testa erro na autenticação do google(retorno de erro)
@pytest.mark.asyncio
@patch("Api.routes.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
async def test_callback_error(mock_authorize):

    # Simulando erro na autorização do Google(com mock)
    mock_authorize.side_effect = Exception("Google error")

    response = client.get(
        "/auth/callback", headers={"host": "localhost"}, follow_redirects=False
    )

    assert response.status_code in (302, 307)
    assert "login-error" in response.headers["location"]
