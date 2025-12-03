import os
import json
import requests
from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

# Importações internas
from jsons_and_dragons import character
# Mantemos a importação, mas vamos usar um wrapper para facilitar o Swagger
from .criar_ficha import get_access_token, get_character_folder_id, load_character_state
from ..gdrive import ensure_path, list_folders_in_parent

router_coleta_ficha = APIRouter()

# --- Configuração ---
ROOT_FOLDER = "JSONs_and_Dragons"
CHARACTERS_FOLDER = "Characters"
FILENAME_PKL = "character_state.pkl"

# --- Segurança para o Swagger ---
# Isso faz aparecer o botão de cadeado no Swagger e garante que o token venha corretamente
security = HTTPBearer()

def obter_token_auth(creds: HTTPAuthorizationCredentials = Depends(security)):
    """
    Este helper pega o token que o Swagger (HTTPBearer) extraiu,
    e reconstrói a string "Bearer <token>" para manter compatibilidade
    com sua função 'get_access_token' original.
    """
    return f"Bearer {creds.credentials}"

@router_coleta_ficha.get("/fichas/")
def listar_todas_fichas(authorization: str = Depends(obter_token_auth)):
    access_token = get_access_token(authorization)

    chars_root_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER])
    existing_folders = list_folders_in_parent(access_token, chars_root_id)
    
    infos = []
    for folder in existing_folders:
        try:
            character, _ = load_character_state(access_token, int(folder['name']))
            infos.append(character.get_basic_infos())
        except Exception as e:
            print(f"Erro ao carregar ficha {folder['name']}: {e}")
            continue
    
    return infos

@router_coleta_ficha.get("/fichas/{id}")
def pegar_ficha(id: int, authorization: str = Depends(obter_token_auth)):
    access_token = get_access_token(authorization)
    
    character, _ = load_character_state(access_token, id)
    return character.get_all()    
        