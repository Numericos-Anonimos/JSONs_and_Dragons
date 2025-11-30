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

def ensure_path(access_token: str, path_list: list):
    """
    Garante que uma estrutura de pastas exista e retorna o ID da última pasta.
    Ex: ensure_path(token, ["JSONs_and_Dragons", "Characters"])
    """
    parent_id = None # Root
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
    file_id = find_file_by_name(access_token, filename, parent_id)
    metadata = {"name": filename, "mimeType": "application/json"}
    
    # Se não existe e temos um pai, definimos o pai na criação
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
        return None