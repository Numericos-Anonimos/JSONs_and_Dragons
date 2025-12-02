import os
import json
from fastapi import APIRouter, HTTPException, Header, Body
from pydantic import BaseModel
from jose import jwt
from typing import Any, List, Union
from urllib.parse import unquote

# Importamos as funções do gdrive
from Api.gdrive import upload_or_update, ensure_path, list_folders_in_parent, get_file_content

# Importamos o parser e a classe Character
from jsons_and_dragons.parser import Character

router_ficha = APIRouter()

# --- Configuração ---
ROOT_FOLDER = "JSONs_and_Dragons"
CHARACTERS_FOLDER = "Characters"
FILENAME_PKL = "character_state.pkl" # Arquivo que guardará a classe Python inteira

# --- Helpers ---
def get_access_token(auth_header: str):
    try:
        token_jwt = auth_header.split(" ")[1]
        payload = jwt.decode(token_jwt, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
        access_token = payload.get("google_access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="Token do Google não encontrado no JWT")
        return access_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Erro de autenticação: {str(e)}")

def get_character_folder_id(access_token: str, char_id: int):
    """Busca a pasta do personagem pelo ID numérico"""
    # Caminho: JSONs_and_Dragons/Characters/{id}
    # Nota: ensure_path pode ser lento se chamado toda vez. 
    # Idealmente você guardaria o ID da pasta Characters em cache ou no JWT.
    return ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(char_id)])

def save_character_state(access_token: str, char_folder_id: str, character: Character):
    """Salva a classe Python serializada no Drive"""
    # Salva as decisões
    json_export = character.to_json()
    upload_or_update(access_token, "decisions.json", json_export, parent_id=char_folder_id)

    # Pega a string base64 do objeto (usando dill/pickle)
    content_str = character.to_pickle_string()
    upload_or_update(access_token, FILENAME_PKL, content_str, parent_id=char_folder_id)

def load_character_state(access_token: str, char_id: int) -> Character:
    """Baixa e restaura a classe Python do Drive"""
    folder_id = get_character_folder_id(access_token, char_id)

    try:    
        try:
            content_base64 = get_file_content(access_token, filename=FILENAME_PKL, parent_id=folder_id)
            character = Character.from_pickle_string(content_base64, access_token)
        except Exception as e:
            decisoes = get_file_content(access_token, filename="decisions.json", parent_id=folder_id)
            character = Character(id=char_id, access_token=access_token, decisions=json.loads(decisoes))
            character.process_queue()
            save_character_state(access_token, folder_id, character)
        
        return character, folder_id
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Personagem {char_id} não encontrado ou arquivo corrompido.")

# --- Modelos de Entrada ---
class AtributosInput(BaseModel):
    forca: int
    destreza: int
    constituicao: int
    inteligencia: int
    sabedoria: int
    carisma: int

class CriarFichaRequest(BaseModel):
    nome: str
    atributos: AtributosInput

class NextDecisionRequest(BaseModel):
    decision: Any # Pode ser string, int, ou lista, dependendo do que o parser pede

# --- Endpoints ---

@router_ficha.post("/ficha/")
def iniciar_ficha(dados: CriarFichaRequest, authorization: str = Header(...)):
    """
    1. Instancia o parser com nome e atributos.
    2. Salva o estado atual (pausado na Raça provavelmente).
    3. Retorna o ID.
    """
    access_token = get_access_token(authorization)
    
    # 1. Encontrar próximo ID (lógica simplificada, idealmente viria de um DB SQL)
    chars_root_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER])
    existing_folders = list_folders_in_parent(access_token, chars_root_id)
    ids = [int(f["name"]) for f in existing_folders if f["name"].isdigit()]
    next_id = max(ids) + 1 if ids else 1
    
    # 2. Prepara as decisões iniciais para o Parser
    # Ordem esperada no seu main(): Nome -> Atributos
    decisoes_iniciais = [
        dados.nome,
        dados.atributos.forca, dados.atributos.destreza, dados.atributos.constituicao,
        dados.atributos.inteligencia, dados.atributos.sabedoria, dados.atributos.carisma
    ]
    
    # 3. Instancia o Personagem
    # Ele vai rodar o __init__, importar metadata e pausar quando precisar de algo (ex: Raça)
    character = Character(id=next_id, access_token=access_token, decisions=decisoes_iniciais)

    print("Rodou character")
    
    # 4. Cria a pasta e Salva o Estado
    char_folder_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(next_id)])
    print("Rodou char_folder_id")
    save_character_state(access_token, char_folder_id, character)

    print("Rodou save_character_state (rodou tudo)")
    print(character)
    
    return {
        "id": next_id,
        "message": "Ficha iniciada com sucesso.",
        "current_status": character.required_decision # Provavelmente estará pedindo nada (fila vazia) ou algo do metadata
    }

@router_ficha.post("/ficha/{char_id}/next")
def avancar_ficha(char_id: int, payload: NextDecisionRequest, authorization: str = Header(...)):
    """
    2. Recebe a resposta pendente, adiciona, processa e salva.
    """
    access_token = get_access_token(authorization)
    
    # 1. Carregar Estado
    character, folder_id = load_character_state(access_token, char_id)
    
    # 2. Adicionar a decisão recebida
    # O parser consome a lista 'decisions' sequencialmente.
    character.data["decisions"].append(payload.decision)
    
    # 3. Rodar a fila até a próxima pausa
    character.process_queue()
    
    # 4. Salvar
    save_character_state(access_token, folder_id, character)
    
    return {
        "required_decision": character.required_decision, # Se {}, acabou
        "logs": "Decisão processada."
    }

@router_ficha.post("/ficha/{char_id}/prev/{n}")
def avancar_ficha(char_id: int, n: int, authorization: str = Header(...)):
    access_token = get_access_token(authorization)
    folder_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(char_id)])

    decisoes = get_file_content(access_token, filename="decisions.json", parent_id=folder_id)

    decisoes = json.loads(decisoes)
    decisoes = decisoes[:-n]
    
    character = Character(id=char_id, access_token=access_token, decisions=decisoes)
    
    if decisoes[character.n] == "Raça":
        character.add_race()
    if decisoes[character.n] == "Background":
        character.add_background()
    if decisoes[character.n] == "Classe":
        character.add_class()
    
    save_character_state(access_token, folder_id, character)
    
    return {
        "required_decision": character.required_decision, # Se {}, acabou
        "logs": "Decisão processada."
    }

@router_ficha.post("/ficha/{char_id}/raca/{raca}")
def definir_raca(char_id: int, raca: str, authorization: str = Header(...)):
    """
    3. Adiciona a Raça e processa.
    """
    access_token = get_access_token(authorization)
    character, folder_id = load_character_state(access_token, char_id)

    # Adiciona a lista ["Raça", raca]
    character.data["decisions"] += ["Raça", raca]
    character.add_race()
    save_character_state(access_token, folder_id, character)
    
    return {
        "message": f"Raça {raca} adicionada.",
        "required_decision": character.required_decision
    }

@router_ficha.post("/ficha/{char_id}/background/{background}")
def definir_background(char_id: int, background: str, authorization: str = Header(...)):
    """
    4. Adiciona Background e processa.
    """
    access_token = get_access_token(authorization)
    
    character, folder_id = load_character_state(access_token, char_id)

    character.data["decisions"] += ["Background", background]
    character.add_background()
    save_character_state(access_token, folder_id, character)
    
    return {
        "message": f"Background {bg_decoded} adicionado.",
        "required_decision": character.required_decision
    }

@router_ficha.post("/ficha/{char_id}/classe/{classe}/{nivel}")
def definir_classe(char_id: int, classe: str, nivel: int, authorization: str = Header(...)):
    """
    5. Adiciona Classe/Nível e processa.
    """
    access_token = get_access_token(authorization)
    
    character, folder_id = load_character_state(access_token, char_id)
    character.data["decisions"] += ["Classe", classe, nivel]
    character.add_class()
    
    save_character_state(access_token, folder_id, character)
    
    return {
        "message": f"Classe {classe} (Nível {nivel}) adicionada.",
        "required_decision": character.required_decision
    }
