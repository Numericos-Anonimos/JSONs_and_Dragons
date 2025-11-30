from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from Api.routes.dados_base import router as base_router
from Api.routes.criar_ficha import router_ficha
from Api.routes.auth import router as auth_router

app = FastAPI()

origins = [
    "http://localhost:4200",
    "https://localhost:4200",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

app.include_router(base_router, prefix="/base")
app.include_router(router_ficha, prefix="/criar")
app.include_router(auth_router, prefix="/auth")