from jose import jwt
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Copie o JWT da URL
jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjb3JyZWlhLnRob21hc0B1bmlmZXNwLmJyIiwibmFtZSI6IlRIT01BUyBQSVJFUyBDT1JSRUlBIiwicGljdHVyZSI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0tLUkx1c2RHVkRQdGJZRjJ2U3pXSGdOaHFsSm9yaUdEdVJRQ1JWaFJEWkN2U1RQR3M9czk2LWMiLCJnb29nbGVfYWNjZXNzX3Rva2VuIjoieWEyOS5hMEFUaTZLMnNFSC1JaUphNWJVdklWNFpNbndydHpscWU0QjBGaWRFazczV213NmFWMG5JblRUM2swZVRfdVVHMWxqSWZDOFFFeWs4QjV3SU55cTN0bDh1WXVRMHJmUjIyOVZ3S2l2a3R6bkVKT2UyMElNbUdTaHdEMTg4cEpQcjBTUjNlVjFGMHRhcEJVSDhHVENrZ3VueWhlVHZzZUFyQ193bmczcmhUOE9kQVZ0OVFpTXBzTEQ1YzhweWhFNlhXUWdLNkJmSUFhQ2dZS0FTVVNBUllTRlFIR1gyTWlqdG5fNDdLbzl3VHJiMkJGLVIweV9nMDIwNiIsImdvb2dsZV9yZWZyZXNoX3Rva2VuIjpudWxsLCJleHAiOjE3NjQ2MTQ3MDZ9.buO6zVcL3NDNyvX3jZCkLXSebcNjz6LRm-eMpSbW7l0"

print(JWT_SECRET, JWT_ALGORITHM)

# Decodifica o JWT
data = jwt.decode(jwt_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
access_token = data["google_access_token"]

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

# Testa criando/atualizando arquivo
resultado = upload_or_update(access_token, "teste.json", '{"teste":123}')
print(resultado)
