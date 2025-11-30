import os
import json
import requests
from Api.gdrive import upload_or_update, find_file_by_name
from fastapi import APIRouter, HTTPException, Header
from jose import jwt

router_coleta_ficha = APIRouter()


@router_coleta_ficha.get("/ficha/")
def coletar_ficha_completa(nome: str, authorization: str = Header(...)):

    try:
        token_jwt = authorization.split(" ")[1]  
        payload = jwt.decode(token_jwt, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM","HS256")])
        access_token = payload.get("google_access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="Token do Google não encontrado no JWT")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"JWT inválido: {str(e)}")


    filename = f"ficha_rpg.json"
    resultado_drive = find_file_by_name(access_token, filename)

    return resultado_drive



