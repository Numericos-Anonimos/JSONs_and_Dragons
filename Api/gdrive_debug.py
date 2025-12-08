import os
import requests
from jose import jwt
from dotenv import load_dotenv

load_dotenv()

def get_token():
    env_token = os.getenv("JWT_TOKEN")
    env_secret = os.getenv("JWT_SECRET")
    if not env_token:
        print("Erro: JWT_TOKEN não encontrado no .env")
        return None
    try:
        payload = jwt.decode(env_token, env_secret, algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
        return payload.get("google_access_token")
    except Exception as e:
        print(f"Erro ao decodificar token: {e}")
        return None

def list_files(token, query):
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "q": query,
        "fields": "files(id, name, mimeType, parents)",
        "pageSize": 100
    }
    res = requests.get(url, headers=headers, params=params)
    if res.status_code != 200:
        print(f"Erro na API: {res.text}")
        return []
    return res.json().get("files", [])

def run_debug():
    token = get_token()
    if not token: return

    print("\n=== 🕵️ INICIANDO VARREDURA DO DRIVE ===")
    
    print(f"\n1. Buscando pastas 'JSONs_and_Dragons'...")
    roots = list_files(token, "name = 'JSONs_and_Dragons' and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    
    if not roots:
        print("❌ Nenhuma pasta 'JSONs_and_Dragons' encontrada!")
        return

    for root in roots:
        print(f"\n📁 PROJETO ENCONTRADO: '{root['name']}' (ID: {root['id']})")
        
        bds = list_files(token, f"name = 'BD' and '{root['id']}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
        
        if not bds:
            print("   └── ❌ Nenhuma pasta 'BD' encontrada aqui.")
        
        for bd in bds:
            print(f"   └── 📁 PASTA BD (ID: {bd['id']})")

            files = list_files(token, f"'{bd['id']}' in parents and trashed = false")
            
            if not files:
                 print("       └── (Pasta Vazia - O script não vê nada aqui!)")
            
            for f in files:
                icon = "📄"
                if "folder" in f['mimeType']: icon = "📁"
                print(f"       └── {icon} '{f['name']}' (ID: {f['id']})")
                
                if f['name'] == 'metadata.json':
                    print("           ✅ ACHEI O METADATA AQUI!")
                    if f['mimeType'] == 'application/vnd.google-apps.document':
                        print("           ⚠️ ALERTA: Isto é um Google Doc, não um arquivo JSON puro!")
    
    print("\n=== FIM DA VARREDURA ===")

if __name__ == "__main__":
    run_debug()