import os
import json
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from jose import jwt
from urllib.parse import unquote

# Importamos as funções novas do gdrive
from Api.gdrive import upload_or_update, ensure_path, list_folders_in_parent, get_file_content

router_ficha = APIRouter()

# --- Configuração de Caminhos Virtuais ---
# Não usamos mais caminhos locais para escrita/leitura do Drive.
ROOT_FOLDER = "JSONs_and_Dragons"
DB_FOLDER = "BD"
CHARACTERS_FOLDER = "Characters"

# Helpers de Token
def get_access_token(auth_header: str):
    try:
        token_jwt = auth_header.split(" ")[1]
        # Decodifica sem verificar assinatura ou verifique conforme sua env
        payload = jwt.decode(token_jwt, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
        access_token = payload.get("google_access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="Token do Google não encontrado no JWT")
        return access_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Erro de autenticação: {str(e)}")

# Helper para ler JSON do Drive (simulando o carregar_json antigo)
def carregar_json_drive(access_token, folder_path_list, filename):
    # Encontra ID da pasta final
    folder_id = ensure_path(access_token, folder_path_list)
    content = get_file_content(access_token, filename=filename, parent_id=folder_id)
    if content is None:
        # Fallback ou erro
        return {} 
    return content

# --- Modelos Pydantic ---
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

@router_ficha.post("/ficha/")
def criar_ficha_base(dados: CriarFichaRequest, authorization: str = Header(...)):
    """
    Cria a ficha direto no Google Drive do usuário.
    """
    access_token = get_access_token(authorization)

    # 1. Garante estrutura de pastas: JSONs_and_Dragons/Characters
    chars_folder_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER])

    # 2. Encontrar o próximo ID disponível (listando pastas)
    existing_folders = list_folders_in_parent(access_token, chars_folder_id)
    ids = []
    for f in existing_folders:
        if f["name"].isdigit():
            ids.append(int(f["name"]))
    
    next_id = max(ids) + 1 if ids else 0

    # 3. Cria a pasta do novo personagem
    new_char_folder_id = ensure_path(access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(next_id)])

    # 4. Montar dados
    decisions = [
        dados.nome,
        dados.atributos.forca, dados.atributos.destreza, dados.atributos.constituicao,
        dados.atributos.inteligencia, dados.atributos.sabedoria, dados.atributos.carisma
    ]
    character_data = {"decisions": decisions}
    content_str = json.dumps(character_data, indent=4, ensure_ascii=False)

    # 5. Upload do character.json na pasta recém criada
    res = upload_or_update(access_token, "character.json", content_str, parent_id=new_char_folder_id)

    return {
        "id": next_id,
        "message": "Personagem criado com sucesso no Google Drive!",
        "drive_response": res
    }

@router_ficha.get("/ficha/classe/{classe}/{nivel}")
def criar_ficha_classe(classe: str, nivel: int):
    dados = carregar_json("classes.json")
    classe_decodificada = unquote(classe)

    if classe_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Classe não encontrada")
    level = f"level_{nivel}"
    if level not in dados[classe_decodificada]:
        raise HTTPException(status_code=400, detail="Nível inválido para a classe")

    bloco = dados[classe_decodificada][level]

    #Pegando todas as operações que seram retornadas para o frontend(usuário ira escolher)
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas

@router_ficha.get("/ficha/raca/{raca}")
def criar_ficha_raca(raca: str):
    dados = carregar_json("races.json")
    raca_decodificada = unquote(raca)

    if raca_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Raça não encontrada")

    bloco = dados[raca_decodificada]

    # Pegando todas as operações que serão retornadas para o frontend
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas

@router_ficha.get("/ficha/subraca/{subraca}")
def criar_ficha_raca(subraca: str):
    dados = carregar_json("subraces.json")
    subraca_decodificada = unquote(subraca)

    if subraca_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Subraça não encontrada")

    bloco = dados[subraca_decodificada]

    # Pegando todas as operações que serão retornadas para o frontend
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas

@router_ficha.get("/ficha/backgrounds/{background}")
def criar_ficha_raca(background: str):
    dados = carregar_json("backgrounds.json")
    background_decodificado = unquote(background)

    if background_decodificado not in dados:
        raise HTTPException(status_code=404, detail="Background não encontrado")

    bloco = dados[background_decodificado]

    #Pegando todas as operações que seram retornadas para o frontend(usuário ira escolher)
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas


if __name__ == "__main__":
    atributos = AtributosInput(forca=15, destreza=14, constituicao=16, inteligencia=12, sabedoria=13, carisma=14)
    criar_ficha_base(CriarFichaRequest(nome="Teste", atributos=atributos))