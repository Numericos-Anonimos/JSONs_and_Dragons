from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from jose import jwt
from datetime import datetime, timedelta
import os

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

REDIRECT_URI = "https://jsons-and-dragons.onrender.com/auth/callback"

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

@router.get("/login")
async def login(request: Request):
    # Determine frontend URL based on host
    host = request.headers.get("host", "")
    if "localhost" in host:
        frontend = "http://localhost:4200/login-success"
    else:
        frontend = "https://jsons-and-dragons.onrender.com/login-success"

    state = {"frontend": frontend}
    return await oauth.google.authorize_redirect(request, redirect_uri=REDIRECT_URI, state=state)

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

        frontend_url = token.get("state", {}).get("frontend", "http://localhost:4200/login-success")
        frontend_url += f"?token={jwt_token}"

        return RedirectResponse(frontend_url)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))