from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from jose import jwt
from datetime import datetime, timedelta
import os
import json
import base64

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
        frontend = "https://jsons-and-dragons-frontend.onrender.com/login-success"

    # Convert state dict to string
    state_dict = {"frontend": frontend}
    state_string = base64.urlsafe_b64encode(
        json.dumps(state_dict).encode()
    ).decode()
    
    return await oauth.google.authorize_redirect(
        request, 
        redirect_uri=REDIRECT_URI, 
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

        state_param = request.query_params.get("state", "")
        try:
            state_dict = json.loads(
                base64.urlsafe_b64decode(state_param.encode()).decode()
            )
            frontend_url = state_dict.get("frontend", "http://localhost:4200/login-success")
        except Exception:
            # Fallback if state decoding fails
            frontend_url = "http://localhost:4200/login-success"

        frontend_url += f"?token={jwt_token}"

        return RedirectResponse(frontend_url)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))