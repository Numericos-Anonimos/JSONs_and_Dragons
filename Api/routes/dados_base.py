from fastapi import APIRouter, Body, Depends

from Api.routes.criar_ficha import get_access_token, obter_token_auth
from jsons_and_dragons.parser import db_handler

router = APIRouter()

# --- Dependência de Banco de Dados ---
def get_db(authorization: str = Depends(obter_token_auth)) -> db_handler:
    """
    Instancia o handler do banco de dados usando o token do usuário.
    Isso conecta ao Drive do usuário para buscar os dados.
    """
    access_token = get_access_token(authorization)
    return db_handler(access_token)

# --- Rota Genérica de Query ---
@router.get("/query")
def execute_query(query: str, db: db_handler = Depends(get_db)):
    """
    Executa qualquer query suportada pelo parser no banco de dados.
    Exemplos:
    - "classes/keys"
    - "items/metadata.type == armor"
    - "spells/Bola de Fogo"
    """
    return db.query(query)

# --- Rotas Específicas (Refatoradas para usar o Drive) ---

@router.get("/classes/keys")
def list_classes(db: db_handler = Depends(get_db)):
    return db.query("classes/keys")

@router.get("/racas/keys")
def list_racas(db: db_handler = Depends(get_db)):
    return db.query("races/keys")

@router.get("/backgrounds/keys")
def list_backgrounds(db: db_handler = Depends(get_db)):
    return db.query("backgrounds/keys")

@router.get("/magias/{classe}/{level}/keys")
def list_magias(classe: str, level: int, db: db_handler = Depends(get_db)):
    # Filtra magias onde a classe está na lista de classes E o nível é igual
    return db.query(f"spells/{classe} in metadata.classes AND metadata.level == {level}/keys")
