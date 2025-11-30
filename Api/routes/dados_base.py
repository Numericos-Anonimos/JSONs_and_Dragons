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

@router.get("/subraca/{raca}/keys")
def list_subclasses(raca: str):
    dados = carregar_json("subclasses.json")
    subracas_filtradas = {
        nome: info
        for nome, info in dados.items()
        if info.get("metadata", {}).get("race") == raca
    }
    return list(subracas_filtradas.keys())







@router.get("/magias/{classe}/{level}/keys")
def list_magias(classe: str, level: int):
    dados = carregar_json("spells.json")

    magias_filtradas = {
        nome: info
        for nome, info in dados.items()
        if classe in info.get("metadata", {}).get("class", []) and level == int(info.get("metadata", {}).get("level", ""))
    }
    return list(magias_filtradas.keys())

@router.get("/idiomas/keys")
def list_armas_keys():
    dados = carregar_json("items.json")

    idiomas = {
        nome: info
        for nome, info in dados.items()
        if "language" in info.get("metadata", {}).get("type", [])
    }
    return list(idiomas.keys())


@router.get("/itens/armaduras/keys")
def list_armaduras_keys():
    dados = carregar_json("items.json")
    armaduras_filtradas = {
        nome: info
        for nome, info in dados.items()
        if "armor" in info.get("metadata", {}).get("type", [])
    }
    return list(armaduras_filtradas.keys())

@router.get("/itens/armaduras/leve/keys")
def list_armaduras_keys():
    dados = carregar_json("items.json")
    armaduras_filtradas = {
        nome: info
        for nome, info in dados.items()
        if "armor" in info.get("metadata", {}).get("type", []) and "Leve" in info.get("metadata", {}).get("category", [])
    }
    return list(armaduras_filtradas.keys())

@router.get("/itens/armaduras/media/keys")
def list_armaduras_keys():
    dados = carregar_json("items.json")
    armaduras_filtradas = {
        nome: info
        for nome, info in dados.items()
        if "armor" in info.get("metadata", {}).get("type", []) and "Média" in info.get("metadata", {}).get("category", [])
    }
    return list(armaduras_filtradas.keys())

@router.get("/itens/armaduras/pesada/keys")
def list_armaduras_keys():
    dados = carregar_json("items.json")
    armaduras_filtradas = {
        nome: info
        for nome, info in dados.items()
        if "armor" in info.get("metadata", {}).get("type", []) and "Pesada" in info.get("metadata", {}).get("category", [])
    }
    return list(armaduras_filtradas.keys())


@router.get("/itens/armas/keys")
def list_armas_keys():
    dados = carregar_json("items.json")

    armas = {
        nome: info
        for nome, info in dados.items()
        if "weapon" in info.get("metadata", {}).get("type", [])
    }
    return list(armas.keys())

@router.get("/itens/armas/marcial/keys")
def list_armas_keys():
    dados = carregar_json("items.json")

    armas = {
        nome: info
        for nome, info in dados.items()
        if "weapon" in info.get("metadata", {}).get("type", []) and "Marcial" in info.get("metadata", {}).get("category", [])
    }
    return list(armas.keys())


@router.get("/itens/armas/simples/keys")
def list_armas_keys():
    dados = carregar_json("items.json")

    armas = {
        nome: info
        for nome, info in dados.items()
        if "weapon" in info.get("metadata", {}).get("type", []) and "Simples" in info.get("metadata", {}).get("category", [])
    }
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

@router.get("/magias/")
def list_racas_full():
    return carregar_json("spells.json")

@router.get("/backgrounds/")
def list_racas_full():
    return carregar_json("backgrounds.json")
