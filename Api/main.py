from fastapi import FastAPI


from Api.routes.dados_base import router as base_router
from Api.routes.criar_ficha import router as router_ficha


app = FastAPI()

# Para testar deve 1º ativar a venv no terminal: . venv/Scripts/activate
# Em seguida rodar o comando: uvicorn Api.main:app --reload

app.include_router(base_router, prefix="/base")
app.include_router(base_router, prefix="/criar")
