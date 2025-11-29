import os
import json
from fastapi import APIRouter, HTTPException
from urllib.parse import unquote

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
BD_DIR = os.path.join(ROOT_DIR, "BD", "dnd_2014")

def carregar_json(nome_arquivo):
    caminho = os.path.join(BD_DIR, nome_arquivo)
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)






@router.get("/racas/")
def list_armaduras():
    dados = carregar_json("races.json")
    return dados



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













