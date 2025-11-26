from fastapi import APIRouter
import os
import json

router = APIRouter()

@router.get("/itens")
def list_itens():
    caminho = os.path.join("BD", "dnd_2014", "items.json")
    with open(caminho, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

@router.get("/classes")
def list_classes():
    caminho = os.path.join("BD", "dnd_2014", "classes.json")
    with open(caminho, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

@router.get("/racas")
def list_racas():
    caminho = os.path.join("BD", "dnd_2014", "races.json")
    with open(caminho, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data