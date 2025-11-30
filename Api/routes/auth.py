from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from jose import jwt
from datetime import datetime, timedelta
import os
import json
import base64
from dotenv import load_dotenv
from Api.gdrive import upload_or_update, find_file_by_name

load_dotenv()


router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

REDIRECT_URIS = {
    "prod": "https://jsons-and-dragons.onrender.com/auth/callback",
    "localhost": "http://localhost:8000/auth/callback",
    "127.0.0.1": "http://127.0.0.1:8000/auth/callback"
}

FRONTEND_URLS = {
    "prod": "https://jsons-and-dragons-frontend.onrender.com",
    "local": "http://localhost:4200"
}

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/drive.file",
        "access_type": "offline",
        "prompt": "consent",
    },
)

def detect_environment(request: Request) -> tuple[str, str]:
    host = request.headers.get("host", "")
    
    host_without_port = host.split(":")[0]
    
    # Verifica localhost
    if host_without_port == "localhost":
        return REDIRECT_URIS["localhost"], FRONTEND_URLS["local"]
    
    # Verifica 127.0.0.1
    if host_without_port == "127.0.0.1":
        return REDIRECT_URIS["127.0.0.1"], FRONTEND_URLS["local"]
    
    # Verifica produção
    if "jsons-and-dragons.onrender.com" in host:
        return REDIRECT_URIS["prod"], FRONTEND_URLS["prod"]
    
    # Fallback
    referer = request.headers.get("referer", "")
    if "localhost" in referer or "127.0.0.1" in referer:
        if "127.0.0.1" in referer:
            return REDIRECT_URIS["127.0.0.1"], FRONTEND_URLS["local"]
        return REDIRECT_URIS["localhost"], FRONTEND_URLS["local"]
    
    # Padrão: produção
    return REDIRECT_URIS["prod"], FRONTEND_URLS["prod"]

@router.get("/login")
async def login(request: Request):
    redirect_uri, frontend_url = detect_environment(request)
    
    # Debug
    print(f"debug")
    print(f"  Host: {request.headers.get('host', '')}")
    print(f"  Redirect URI: {redirect_uri}")
    print(f"  Frontend URL: {frontend_url}")
    print(f"  Client ID: {GOOGLE_CLIENT_ID[:20]}..." if GOOGLE_CLIENT_ID else "None")
    print(f"  Client Secret: {'Client secret ok' if GOOGLE_CLIENT_SECRET else 'None'}")
    
    state_data = {
        "frontend": f"{frontend_url}/login-success",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    state_string = base64.urlsafe_b64encode(
        json.dumps(state_data).encode()
    ).decode()

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri=redirect_uri,
        state=state_string
    )

@router.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        access_token = token.get("access_token")
        refresh_token = token.get("refresh_token")

        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")

        jwt_token = jwt.encode(
            {
                "sub": user_info["email"],
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
                "google_access_token": access_token,
                "google_refresh_token": refresh_token,
                "exp": datetime.utcnow() + timedelta(hours=24),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )

        # Recupera o frontend URL do state
        state_string = request.query_params.get("state", "")
        frontend_url = None
        
        if state_string:
            try:
                state_data = json.loads(
                    base64.urlsafe_b64decode(state_string.encode()).decode()
                )
                frontend_url = state_data.get("frontend")
            except Exception as e:
                print(f"Erro ao decodificar state: {e}")

        # Fallback
        if not frontend_url:
            _, frontend_base = detect_environment(request)
            frontend_url = f"{frontend_base}/login-success"

        result = upload_or_update(access_token, "teste.json", '{"teste": 123}')
        # Adiciona o token à URL
        redirect_url = f"{frontend_url}?token={jwt_token}"
        return RedirectResponse(redirect_url)

    except Exception as e:
        print(f"Erro no callback: {str(e)}")
        _, frontend_base = detect_environment(request)
        error_url = f"{frontend_base}/login-error?error={str(e)}"
        return RedirectResponse(error_url)