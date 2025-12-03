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

# --- Endpoints ---

@router_coleta_ficha.get("/ficha/")
def coletar_ficha_unica(nome: str, authorization: str = Depends(obter_token_auth)):
    # Mudei o nome da função para 'coletar_ficha_unica' para não conflitar
    access_token = get_access_token(authorization)

    filename = f"ficha_rpg.json"
    # Nota: filename hardcoded aqui pode ser um problema se a ficha não tiver esse nome exato
    # ou se você quiser buscar pelo 'nome' passado no parametro.
    # Assumindo que você quer buscar pelo nome do arquivo:
    if nome:
        # Se a intenção era usar o parametro 'nome' para achar o arquivo:
        # filename = f"{nome}.json" 
        pass 
        
    resultado_drive = get_file_content(access_token, filename)
    return resultado_drive


@router_coleta_ficha.get("/fichas/")
def listar_todas_fichas(authorization: str = Depends(obter_token_auth)):
    # Mudei o nome da função para 'listar_todas_fichas'
    access_token = get_access_token(authorization)

    # Percorrer a pasta Characters, pegar as informações basicas de cada um, e retornar
    chars_root_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER])
    existing_folders = list_folders_in_parent(access_token, chars_root_id)
    
    infos = []
    for folder in existing_folders:
        # Verifica se o nome da pasta é um número (ID do personagem) para evitar erros
        if folder['name'].isdigit():
            try:
                char_obj, _ = load_character_state(access_token, int(folder['name']))
                infos.append(char_obj.get_basic_infos())
            except Exception as e:
                print(f"Erro ao carregar ficha {folder['name']}: {e}")
                continue
                
    return infos