import os
import json
from fastapi import APIRouter, HTTPException
from urllib.parse import unquote

router_ficha = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
BD_DIR = os.path.join(ROOT_DIR, "BD", "dnd_2014")

def carregar_json(nome_arquivo):
    caminho = os.path.join(BD_DIR, nome_arquivo)
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


@router_ficha.post("/ficha/classe/{classe}/{nivel}")
def criar_ficha_classe(classe: str, nivel: int):
    dados = carregar_json("classes.json")
    classe_decodificada = unquote(classe)

    if classe_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Classe não encontrada")
    
    level = f"level_{nivel}"
    if level not in dados[classe_decodificada]:
        raise HTTPException(status_code=400, detail="Nível inválido para a classe")

    return dados[classe_decodificada][level]







@router_ficha.post("/ficha/atributos")
def criar_ficha_atributos_selecionado(valores: dict):

    atributos_esperados = {"Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"}

    if set(valores.keys()) != atributos_esperados:
        raise HTTPException(
            status_code=400,
            detail=f"Atributos inválidos. Esperado: {atributos_esperados}"
        )

    for nome, valor in valores.items():
        if not isinstance(valor, int):
            raise HTTPException(
                status_code=400,
                detail=f"O atributo '{nome}' deve ser um inteiro."
            )
        if not (3 <= valor <= 18):
            raise HTTPException(
                status_code=400,
                detail=f"O atributo '{nome}' deve estar entre 3 e 18. Recebido: {valor}"
            )

    ficha_atributos = {
        "type": "BASE_CHARACTER",
        "operations": [
            {"action": "SET", "property": "Força_base",        "value": valores["Força"]},
            {"action": "SET", "property": "Destreza_base",     "value": valores["Destreza"]},
            {"action": "SET", "property": "Constituição_base", "value": valores["Constituição"]},
            {"action": "SET", "property": "Inteligência_base", "value": valores["Inteligência"]},
            {"action": "SET", "property": "Sabedoria_base",    "value": valores["Sabedoria"]},
            {"action": "SET", "property": "Carisma_base",      "value": valores["Carisma"]}
        ]
    }

    return ficha_atributos
