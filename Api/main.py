from fastapi import FastAPI
from Api.routes.dados_base import router as base_router

app = FastAPI()

app.include_router(base_router, prefix="/base")