import json
import os
from typing import Any, List, Union

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from pydantic import BaseModel

from Api.gdrive import (
    ensure_path,
    get_file_content,
    list_folders_in_parent,
    upload_or_update,
)

from jsons_and_dragons import Character

router_ficha = APIRouter()

# --- Configuração ---
ROOT_FOLDER = "JSONs_and_Dragons"
CHARACTERS_FOLDER = "Characters"
FILENAME_PKL = "character_state.pkl"

security = HTTPBearer()


def obter_token_auth(creds: HTTPAuthorizationCredentials = Depends(security)):
    """
    Reconstrói o formato 'Bearer <token>' para manter compatibilidade
    com a função get_access_token existente.
    """
    return f"Bearer {creds.credentials}"


# --- Helpers ---
def get_access_token(auth_header: str):
    try:
        # Como o wrapper já garante o formato, o split continua funcionando
        token_jwt = auth_header.split(" ")[1]
        payload = jwt.decode(
            token_jwt,
            os.getenv("JWT_SECRET"),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
        )
        access_token = payload.get("google_access_token")
        if not access_token:
            raise HTTPException(
                status_code=401, detail="Token do Google não encontrado no JWT"
            )
        return access_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Erro de autenticação: {str(e)}")


def get_character_folder_id(access_token: str, char_id: int):
    """Busca a pasta do personagem pelo ID numérico"""
    return ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(char_id)])


def save_character_state(access_token: str, char_folder_id: str, character: Character):
    """Salva a classe Python serializada no Drive"""
    json_export = character.to_json()
    upload_or_update(
        access_token, "decisions.json", json_export, parent_id=char_folder_id
    )

    content_str = character.to_pickle_string()
    upload_or_update(access_token, FILENAME_PKL, content_str, parent_id=char_folder_id)


def load_character_state(access_token: str, char_id: int) -> Character:
    """Baixa e restaura a classe Python do Drive"""
    folder_id = get_character_folder_id(access_token, char_id)

    try:
        content_base64 = get_file_content(
            access_token, filename=FILENAME_PKL, parent_id=folder_id
        )
        if content_base64:
            character = Character.from_pickle_string(content_base64, access_token)
        else:
            decisoes = get_file_content(
                access_token, filename="decisions.json", parent_id=folder_id
            )
            character = Character(
                id=char_id, access_token=access_token, decisions=decisoes
            )
            if character.n < len(decisoes) and decisoes[character.n] == "Raça":
                character.add_race()
            if character.n < len(decisoes) and decisoes[character.n] == "Background":
                character.add_background()
            while character.n < len(decisoes) and decisoes[character.n] == "Classe":
                character.add_class()
            save_character_state(access_token, folder_id, character)
        return character, folder_id
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Personagem {char_id} não encontrado ou arquivo corrompido.",
        )


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
    decision: Union[str, int, list]


# --- Endpoints ---
@router_ficha.post("/ficha/")
def iniciar_ficha(
    dados: CriarFichaRequest, authorization: str = Depends(obter_token_auth)
):
    """
    1. Instancia o parser com nome e atributos.
    2. Salva o estado atual (pausado na Raça provavelmente).
    3. Retorna o ID.
    """
    access_token = get_access_token(authorization)

    # 1. Encontrar próximo ID
    chars_root_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER])
    existing_folders = list_folders_in_parent(access_token, chars_root_id)
    ids = [int(f["name"]) for f in existing_folders if f["name"].isdigit()]
    next_id = max(ids) + 1 if ids else 1

    # 2. Prepara as decisões iniciais para o Parser
    decisoes_iniciais = [
        dados.nome,
        dados.atributos.forca,
        dados.atributos.destreza,
        dados.atributos.constituicao,
        dados.atributos.inteligencia,
        dados.atributos.sabedoria,
        dados.atributos.carisma,
    ]

    # 3. Instancia o Personagem
    character = Character(
        id=next_id, access_token=access_token, decisions=decisoes_iniciais
    )

    print("Rodou character")

    # 4. Cria a pasta e Salva o Estado
    char_folder_id = ensure_path(
        access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(next_id)]
    )
    print("Rodou char_folder_id")
    save_character_state(access_token, char_folder_id, character)

    print("Rodou save_character_state (rodou tudo)")
    print(character)

    return {
        "id": next_id,
        "message": "Ficha iniciada com sucesso.",
        "current_status": character.required_decision,
    }


@router_ficha.post("/ficha/{char_id}/next")
def avancar_ficha(
    char_id: int,
    payload: NextDecisionRequest,
    authorization: str = Depends(obter_token_auth),
):
    """
    2. Recebe a resposta pendente, adiciona, processa e salva.
    """
    access_token = get_access_token(authorization)

    character, folder_id = load_character_state(access_token, char_id)

    character.data["decisions"].append(payload.decision)

    character.process_queue()

    save_character_state(access_token, folder_id, character)

    return {
        "required_decision": character.required_decision,
        "logs": "Decisão processada.",
    }


@router_ficha.post("/ficha/{char_id}/prev/{n}")
def retroceder_ficha(
    char_id: int, n: int, authorization: str = Depends(obter_token_auth)
):

    access_token = get_access_token(authorization)
    folder_id = ensure_path(
        access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(char_id)]
    )

    decisoes = get_file_content(
        access_token, filename="decisions.json", parent_id=folder_id
    )
    print(decisoes)
    # decisoes = json.loads(decisoes)
    decisoes = decisoes[:-n]

    character = Character(id=char_id, access_token=access_token, decisions=decisoes)

    if character.n < len(decisoes) and decisoes[character.n] == "Raça":
        character.add_race()
    if character.n < len(decisoes) and decisoes[character.n] == "Background":
        character.add_background()
    while character.n < len(decisoes) and decisoes[character.n] == "Classe":
        character.add_class()

    save_character_state(access_token, folder_id, character)

    return {
        "required_decision": character.required_decision,  # Se {}, acabou
        "logs": "Decisão processada.",
    }


@router_ficha.post("/ficha/{char_id}/raca/{raca}")
def definir_raca(
    char_id: int, raca: str, authorization: str = Depends(obter_token_auth)
):
    """Adiciona a Raça e processa"""
    access_token = get_access_token(authorization)
    character, folder_id = load_character_state(access_token, char_id)

    character.data["decisions"] += ["Raça", raca]
    character.add_race()
    save_character_state(access_token, folder_id, character)

    return {
        "message": f"Raça {raca} adicionada.",
        "required_decision": character.required_decision,
    }


@router_ficha.post("/ficha/{char_id}/background/{background}")
def definir_background(
    char_id: int, background: str, authorization: str = Depends(obter_token_auth)
):
    """
    4. Adiciona Background e processa.
    """
    access_token = get_access_token(authorization)

    character, folder_id = load_character_state(access_token, char_id)

    character.data["decisions"] += ["Background", background]
    character.add_background()
    save_character_state(access_token, folder_id, character)

    return {
        "message": f"Background {background} adicionado.",
        "required_decision": character.required_decision,
    }


@router_ficha.post("/ficha/{char_id}/classe/{classe}/{nivel}")
def definir_classe(
    char_id: int,
    classe: str,
    nivel: int,
    authorization: str = Depends(obter_token_auth),
):
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
        "required_decision": character.required_decision,
    }


@router_ficha.post("/ficha/import")
async def importar_ficha(
    file: UploadFile = File(...), authorization: str = Depends(obter_token_auth)
):
    """
    Faz upload de um arquivo .json (decisions.json) e cria um novo personagem
    a partir dele.
    """
    access_token = get_access_token(authorization)

    # 1. Ler e validar o arquivo
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="O arquivo deve ser um .json")

    try:
        content = await file.read()
        decisions = json.loads(content)

        if not isinstance(decisions, list):
            raise HTTPException(
                status_code=400,
                detail="O formato do JSON deve ser uma lista de decisões.",
            )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Arquivo JSON inválido.")

    # 2. Encontrar próximo ID (mesma lógica do iniciar_ficha)
    chars_root_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER])
    existing_folders = list_folders_in_parent(access_token, chars_root_id)
    ids = [int(f["name"]) for f in existing_folders if f["name"].isdigit()]
    next_id = max(ids) + 1 if ids else 1

    print(f"Importando arquivo '{file.filename}' para o ID: {next_id}")

    try:
        # 3. Processar o personagem com as decisões do arquivo
        character = Character(
            id=next_id, access_token=access_token, decisions=decisions
        )

        # 4. Salvar no Drive (Cria a pasta e salva os arquivos)
        char_folder_id = ensure_path(
            access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(next_id)]
        )
        save_character_state(access_token, char_folder_id, character)

        return {
            "id": next_id,
            "message": "Ficha importada com sucesso.",
            "current_status": character.required_decision,
        }

    except Exception as e:
        print(f"Erro na importação: {e}")
        raise HTTPException(
            status_code=500, detail=f"Falha ao processar a importação: {str(e)}"
        )
