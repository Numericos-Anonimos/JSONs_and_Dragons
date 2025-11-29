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



# Listas de chaves para seleção no frontend
@router.get("/classes/keys")
def list_classes():
    dados = carregar_json("classes.json")
    return list(dados.keys())

@router.get("/subclasses/{classe}/keys")
def list_subclasses(classe: str):
    dados = carregar_json("subclasses.json")
    subclasses_filtradas = {
        nome: info
        for nome, info in dados.items()
        if info.get("metadata", {}).get("class") == classe
    }
    return list(subclasses_filtradas.keys())

@router.get("/racas/keys")
def list_racas():
    dados = carregar_json("races.json")
    return list(dados.keys())

@router.get("/magias/{classe}/keys")
def list_magias(classe: str):
    dados = carregar_json("spells.json")

    magias_filtradas = {
        nome: info
        for nome, info in dados.items()
        if classe in info.get("metadata", {}).get("class", [])
    }
    return list(magias_filtradas.keys())

@router.get("/itens/armaduras/keys")
def list_armaduras_keys():
    dados = carregar_json("items.json")
    armaduras = dados.get("Armaduras", {})
    return list(armaduras.keys())

@router.get("/itens/armas/keys")
def list_armas_keys():
    dados = carregar_json("items.json")
    armas = dados.get("Armas", {})
    return list(armas.keys())


# Endpoints completos de cada categoria
@router.get("/itens/")
def list_itens():
    return carregar_json("items.json")


@router.get("/classes/")
def list_classes_full():
    return carregar_json("classes.json")


@router.get("/racas/")
def list_racas_full():
    return carregar_json("races.json")


@router.get("/itens/armaduras")
def list_armaduras():
    dados = carregar_json("items.json")
    return dados.get("Armaduras", [])

@router.get("/itens/armaduras/{nome}")
def pegar_armadura(nome: str):
    dados = carregar_json("items.json")
    armaduras = dados.get("Armaduras", {})

    if nome not in armaduras:
        raise HTTPException(status_code=404, detail="Armadura não encontrada")

    return armaduras[nome]

@router.get("/itens/armas")
def list_armas():
    dados = carregar_json("items.json")
    return dados.get("Armas", [])


@router.get("/armas/{nome}")
def pegar_arma(nome: str):
    dados = carregar_json("items.json")
    armas = dados.get("Armas", {})

    return armas.get(nome, {"erro": "Arma não encontrada"})


@router.get("/itens/equipamentosaventura")
def list_equipamentos_aventura():
    dados = carregar_json("items.json")
    return dados.get("Equipamento de Aventura", [])
