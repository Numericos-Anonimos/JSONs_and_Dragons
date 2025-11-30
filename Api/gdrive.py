from jose import jwt
import os
import json
import requests

# Função para criar/atualizar arquivo
def find_file_by_name(access_token: str, filename: str):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"name = '{filename}' and trashed = false",
        "fields": "files(id, name)"
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, params=params)
    files = r.json().get("files", [])
    return files[0]["id"] if files else None


# Função para criar ou atualizar arquivo no Google Drive do usuário (acesstoken necessário)
def upload_or_update(access_token: str, filename: str, content: str):
    file_id = find_file_by_name(access_token, filename)
    metadata = {"name": filename, "mimeType": "application/json"}
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


