from jose import jwt
import os
import json
import requests


# --- Helpers de Navegação ---
def find_file_by_name(access_token: str, filename: str, parent_id: str = None, mime_type: str = None):
    """Busca um arquivo pelo nome, opcionalmente dentro de uma pasta específica."""
    url = "https://www.googleapis.com/drive/v3/files"
    
    q = f"name = '{filename}' and trashed = false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    if mime_type:
        q += f" and mimeType = '{mime_type}'"

    params = {
        "q": q,
        "fields": "files(id, name, mimeType)",
        "pageSize": 1
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, params=params)
    files = r.json().get("files", [])
    return files[0]["id"] if files else None

def create_folder(access_token: str, folder_name: str, parent_id: str = None):
    """Cria uma pasta e retorna o ID."""
    url = "https://www.googleapis.com/drive/v3/files"
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    if parent_id:
        metadata["parents"] = [parent_id]
        
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.post(url, headers=headers, json=metadata)
    return r.json().get("id")

def find_or_create_folder(access_token: str, folder_name: str, parent_id: str = None):
    """Busca uma pasta ou cria se não existir."""
    folder_id = find_file_by_name(access_token, folder_name, parent_id, "application/vnd.google-apps.folder")
    if folder_id:
        return folder_id
    return create_folder(access_token, folder_name, parent_id)

def ensure_path(access_token: str, path_list: list):
    """
    Garante que uma estrutura de pastas exista e retorna o ID da última pasta.
    Ex: ensure_path(token, ["JSONs_and_Dragons", "Characters"])
    """
    parent_id = None 
    for folder in path_list:
        found_id = find_file_by_name(access_token, folder, parent_id, "application/vnd.google-apps.folder")
        if not found_id:
            found_id = create_folder(access_token, folder, parent_id)
        parent_id = found_id
    return parent_id

def list_folders_in_parent(access_token: str, parent_id: str):
    """Lista todas as pastas dentro de um pai (usado para pegar IDs dos personagens)."""
    url = "https://www.googleapis.com/drive/v3/files"
    q = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    params = {
        "q": q,
        "fields": "files(id, name)"
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("files", [])

# --- Upload e Download ---
def upload_or_update(access_token: str, filename: str, content: str, parent_id: str = None):
    """Faz upload de um arquivo JSON ou atualiza se já existir."""
    file_id = find_file_by_name(access_token, filename, parent_id)
    metadata = {"name": filename, "mimeType": "application/json"}
    
    if not file_id and parent_id:
        metadata["parents"] = [parent_id]

    files = {
        "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
        "file": (filename, content, "application/json")
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    
    if file_id:
        url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=multipart"
        r = requests.patch(url, headers=headers, files=files)
        return {"status": "updated", "file_id": file_id, "google": r.json()}
    else:
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
        r = requests.post(url, headers=headers, files=files)
        return {"status": "created", "google": r.json()}
    
def get_file_content(access_token: str, file_id: str = None, filename: str = None, parent_id: str = None):
    """
    Baixa conteúdo. Pode usar o ID direto (mais rápido) ou procurar por nome/pai.
    """
    target_id = file_id
    if not target_id and filename:
        target_id = find_file_by_name(access_token, filename, parent_id)
    
    if not target_id:
        print(f"Erro: Arquivo '{filename}' não encontrado no Drive.")
        return None  

    url = f"https://www.googleapis.com/drive/v3/files/{target_id}?alt=media"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        try:
            return r.json()  
        except json.JSONDecodeError:
            return r.text  
    else:
        print(f"Erro ao baixar '{filename or target_id}': Status {r.status_code}")
        print(f"Detalhe do erro: {r.text}")
        return None

# --- Funções de Setup ---
def upload_specific_folders(access_token: str, local_bd_path: str, drive_bd_id: str):
    """
    Envia apenas pastas específicas do BD local para o Google Drive.
    """
    
    folders_to_upload = ["dnd_2014", "tasha_cauldron", "xanatar_guide"]

    for folder_name in folders_to_upload:
        local_folder_path = os.path.join(local_bd_path, folder_name)
        if not os.path.exists(local_folder_path):
            continue


        drive_folder_id = find_or_create_folder(access_token, folder_name, parent_id=drive_bd_id)

        for root, dirs, files in os.walk(local_folder_path):
            rel_path = os.path.relpath(root, local_folder_path)
            current_parent_id = drive_folder_id

            if rel_path != ".":
                for subfolder in rel_path.split(os.sep):
                    current_parent_id = find_or_create_folder(access_token, subfolder, parent_id=current_parent_id)

            for file in files:
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                upload_or_update(access_token, file, content, current_parent_id)

def setup_drive_structure(access_token: str):
    """
    Cria pasta raiz e subpastas principais.
    Copia o BD local para o Drive apenas se a pasta BD ainda não existir.
    Inclui o upload do metadata.json do BD.
    """
    root_id = find_or_create_folder(access_token, "JSONs_and_Dragons")

    bd_id = find_or_create_folder(access_token, "BD", parent_id=root_id)
    char_id = find_or_create_folder(access_token, "Characters", parent_id=root_id)

    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(ROOT_DIR, ".."))
    local_bd_path = os.path.join(ROOT_DIR, "BD")

    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "q": f"name='BD' and '{root_id}' in parents and trashed=false",
        "fields": "files(id, name)"
    }
    r = requests.get(url, headers=headers, params=params)
    files = r.json().get("files", [])

    if files and len(files) == 1:
        metadata_path = os.path.join(local_bd_path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata_content = f.read()
            upload_or_update(access_token, "metadata.json", metadata_content, bd_id)
    
        upload_specific_folders(access_token, local_bd_path, bd_id)

    return {
        "root": root_id,
        "bd": bd_id,
        "characters": char_id
    }