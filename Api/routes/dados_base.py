import os
import json
from fastapi import APIRouter, HTTPException
from urllib.parse import unquote

# Para testar deve 1º ativar a venv no terminal: . venv/Scripts/activate
# Em seguida rodar o comando: uvicorn Api.main:app --reload

router = APIRouter()

# Base do arquivo atual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Sobe dois níveis: routes → Api → JSONs_and_Dragons
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

BD_DIR = os.path.join(ROOT_DIR, "BD", "dnd_2014")

def carregar_json(nome_arquivo):
    caminho = os.path.join(BD_DIR, nome_arquivo)
    print("Lendo arquivo:", caminho)  # debug opcional
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)






# Rota Inicial da API

@router.get("/itens/")
def list_itens():
    return carregar_json("items.json")

#Trabalhando com armaduras

@router.get("/itens/armaduras")
def list_armaduras():
    dados = carregar_json("items.json")
    return dados.get("Armaduras", [])

@router.get("/armaduras/keys")
def armaduras_keys():
    dados = carregar_json("items.json")
    armaduras = dados.get("Armaduras", {})
    return {"count": len(armaduras), "keys_preview": list(armaduras.keys())[:50]}

@router.get("/itens/armaduras/{nome}")
def pegar_armadura(nome: str):
    dados = carregar_json("items.json")
    armaduras = dados.get("Armaduras", {})
    if nome not in armaduras:
        raise HTTPException(status_code=404, detail="Armadura não encontrada")
    return armaduras[nome]




#Trabalhando com armas

@router.get("/itens/armas")
def list_armas():
    dados = carregar_json("items.json")
    return dados.get("Armas", [])

@router.get("/armas/{nome}")
def pegar_arma(nome: str):
    dados = carregar_json("items.json")
    armas = dados.get("Armas", {})
    return armas.get(nome, {"erro": "Arma não encontrada"})





#Trabalhando com equipamentos de aventura

@router.get("/itens/equipamentosaventura")
def list_equipamentos_aventura():
    dados = carregar_json("items.json")
    return dados.get("Equipamento de Aventura", [])













