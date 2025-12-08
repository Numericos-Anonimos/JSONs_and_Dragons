import os
import json
import zipfile
import io
import shutil
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

# Importações do projeto
from Api.gdrive import (
    upload_or_update, 
    find_file_by_name, 
    ensure_path, 
    get_file_content, 
    find_or_create_folder
)

router_homebrew = APIRouter()
security = HTTPBearer()

# --- Configurações ---
ROOT_FOLDER = "JSONs_and_Dragons"
BD_FOLDER = "BD"
METADATA_FILE = "metadata.json"

# --- Helpers de Autenticação ---
def obter_token_auth(creds: HTTPAuthorizationCredentials = Depends(security)):
    return f"Bearer {creds.credentials}"

def get_access_token(auth_header: str):
    try:
        token_jwt = auth_header.split(" ")[1]
        payload = jwt.decode(
            token_jwt, 
            os.getenv("JWT_SECRET"), 
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")]
        )
        access_token = payload.get("google_access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="Token do Google não encontrado.")
        return access_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Erro de autenticação: {str(e)}")

# --- Lógica de Upload Recursivo ---
def upload_extracted_files(access_token: str, base_folder_id: str, zip_ref: zipfile.ZipFile):
    """
    Percorre os arquivos do ZIP e os envia para o Google Drive, 
    recriando a estrutura de pastas.
    """
    # Lista todos os arquivos no zip
    for file_info in zip_ref.infolist():
        if file_info.is_dir():
            continue
        
        # Caminho relativo do arquivo no zip (ex: "pastas/arquivo.json")
        path_parts = file_info.filename.split('/')
        filename = path_parts[-1]
        folders = path_parts[:-1]
        
        # Ignora arquivos ocultos ou de sistema se necessário (opcional)
        if filename.startswith('.') or filename == "":
            continue

        # Navega/Cria pastas no Drive até chegar no destino
        current_parent_id = base_folder_id
        for folder_name in folders:
            current_parent_id = find_or_create_folder(access_token, folder_name, parent_id=current_parent_id)
        
        # Lê o conteúdo do arquivo
        with zip_ref.open(file_info) as f:
            content = f.read().decode('utf-8', errors='replace') # Assume UTF-8 para JSONs
            
        # Faz o upload
        print(f"Enviando {file_info.filename}...")
        upload_or_update(access_token, filename, content, parent_id=current_parent_id)

@router_homebrew.post("/upload")
async def upload_homebrew(
    name: str = Form(...),
    file: UploadFile = File(...),
    authorization: str = Depends(obter_token_auth)
):
    """
    Recebe um ZIP e um Nome.
    1. Atualiza metadata.json no Drive (adiciona o módulo se não existir).
    2. Cria a pasta do módulo em BD/.
    3. Descompacta e envia os arquivos do ZIP para essa pasta.
    """
    access_token = get_access_token(authorization)

    # 1. Validar arquivo
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="O arquivo deve ser um ZIP.")

    try:
        # 2. Localizar pasta BD no Drive
        bd_folder_id = ensure_path(access_token, [ROOT_FOLDER, BD_FOLDER])
        if not bd_folder_id:
            raise HTTPException(status_code=500, detail="Pasta do Banco de Dados não encontrada no Drive.")

        # 3. Ler e Atualizar metadata.json
        metadata_content = get_file_content(access_token, filename=METADATA_FILE, parent_id=bd_folder_id)
        
        if isinstance(metadata_content, str):
            metadata_json = json.loads(metadata_content)
        else:
            metadata_json = metadata_content or {"modules": []}
            
        modules_list = metadata_json.get("modules", [])
        
        is_new_module = name not in modules_list
        if is_new_module:
            modules_list.append(name)
            metadata_json["modules"] = modules_list
            # Atualiza o metadata.json no Drive
            upload_or_update(
                access_token, 
                METADATA_FILE, 
                json.dumps(metadata_json, indent=4), 
                parent_id=bd_folder_id
            )

        # 4. Preparar pasta do Módulo (Sobrescreve conteúdo se já existir, pois o upload faz update)
        module_folder_id = find_or_create_folder(access_token, name, parent_id=bd_folder_id)

        # 5. Processar o ZIP em memória
        content = await file.read()
        with zipfile.ZipFile(io.BytesIO(content)) as zip_ref:
            # Valida se há arquivos maliciosos ou muito grandes aqui se necessário
            upload_extracted_files(access_token, module_folder_id, zip_ref)

        return {
            "message": f"Homebrew '{name}' processada com sucesso.",
            "status": "created" if is_new_module else "updated",
            "modules": modules_list
        }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Arquivo ZIP inválido ou corrompido.")
    except Exception as e:
        print(f"Erro no upload de homebrew: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar homebrew: {str(e)}")
