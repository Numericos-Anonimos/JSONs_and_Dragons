from jose import jwt
import os
import json
import requests


def find_or_create_folder(access_token: str, folder_name: str, parent_id: str = None):
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    params = {"q": query, "fields": "files(id, name)"}
    r = requests.get(url, headers=headers, params=params)
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]

    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]

    r = requests.post(url, headers=headers, json=metadata)
    if r.status_code in [200, 201]:
        return r.json().get("id")
    else:
        print("Erro ao criar pasta:", r.status_code, r.text)
        return None

def upload_or_update(access_token: str, filename: str, content: str, parent_id: str):
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "q": f"name='{filename}' and '{parent_id}' in parents and trashed=false",
        "fields": "files(id, name)"
    }
    r = requests.get(url, headers=headers, params=params)
    files = r.json().get("files", [])
    file_id = files[0]["id"] if files else None

    metadata = {"name": filename, "mimeType": "application/json", "parents": [parent_id]}
    files_data = {
        "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
        "file": (filename, content, "application/json")
    }

    if file_id:
        url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=multipart"
        r = requests.patch(url, headers=headers, files=files_data)
        return {"status": "updated", "file_id": file_id, "google": r.json()}
    else:
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
        r = requests.post(url, headers=headers, files=files_data)
        return {"status": "created", "google": r.json()}
    
def upload_specific_folders(access_token: str, local_bd_path: str, drive_bd_id: str):
    """
    Envia apenas pastas específicas do BD local para o Google Drive.
    """
    
    folders_to_upload = ["dnd_2014", "tasha_cauldron", "xanatar-guide.json"]

    for folder_name in folders_to_upload:
        local_folder_path = os.path.join(local_bd_path, folder_name)
        if not os.path.exists(local_folder_path):
            continue

        # Cria a pasta no Drive
        drive_folder_id = find_or_create_folder(access_token, folder_name, parent_id=drive_bd_id)

        # Faz upload de todos os arquivos dentro dessa pasta
        for root, dirs, files in os.walk(local_folder_path):
            # Mantém a estrutura de subpastas
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
    """
    root_id = find_or_create_folder(access_token, "JSONs_and_Dragons")

    # Tenta criar BD e Characters. Se BD já existir, find_or_create_folder retorna o ID existente
    bd_id = find_or_create_folder(access_token, "BD", parent_id=root_id)
    char_id = find_or_create_folder(access_token, "Characters", parent_id=root_id)

    # Caminho do BD local
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(ROOT_DIR, ".."))
    local_bd_path = os.path.join(ROOT_DIR, "BD")

    # Verifica se a pasta BD era recém-criada
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "q": f"name='BD' and '{root_id}' in parents and trashed=false",
        "fields": "files(id, name)"
    }
    r = requests.get(url, headers=headers, params=params)
    files = r.json().get("files", [])

    if files and len(files) == 1:
        upload_specific_folders(access_token, local_bd_path, bd_id)

    return {
        "root": root_id,
        "bd": bd_id,
        "characters": char_id
    }



















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