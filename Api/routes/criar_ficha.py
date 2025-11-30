import os
import json
import requests
from Api.gdrive import upload_or_update, find_file_by_name
from fastapi import APIRouter, HTTPException, Header
from urllib.parse import unquote
from jose import jwt
from pydantic import BaseModel

#   uvicorn Api.main:app --reload --host localhost --port 8000

router_ficha = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
BD_DIR = os.path.join(ROOT_DIR, "BD", "dnd_2014")
CHARACTERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), r"BD\characters")

def carregar_json(nome_arquivo):
    caminho = os.path.join(BD_DIR, nome_arquivo)
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

class AtributosInput(BaseModel):
    forca: int
    destreza: int
    constituicao: int
    inteligencia: int
    sabedoria: int
    carisma: int

class CriarFichaRequest(BaseModel):
    nome: str
    atributos: AtributosInput



# A lógica abaixo cria uma lista linear (flat) de escolhas, preservando a ordem
# de leitura da ficha. Cada bloco CHOOSE_* ganha um campo "relacao", que indica
# quantos blocos filhos diretos aparecem logo após ele na lista final. O front
# usa “relacao” para saber quantas posições deve avançar ao exibir os níveis
# seguintes, sem precisar navegar a árvore original ou trabalhar com IDs. Assim,
# basta consumir a lista sequencialmente, pulando a quantidade indicada em cada
# "relacao[i]" para chegar ao próximo bloco irmão.

def encontrar_escolhas(ops):
    resultados = []

    for op in ops:
        if not isinstance(op, dict):
            continue

        action = op.get("action")

        # CHOOSE_MAP
        if action == "CHOOSE_MAP":
            options = op.get("options", [])
            relacao = [0] * len(options)

            resultados.append({
                "label": op.get("label", ""),
                "opcoes": options,
                "n": op.get("n"),
                "tam": len(options),
                "relacao": relacao,
                "offsets": [0] * len(options)   # offsets triviais
            })

        # CHOOSE_OPERATIONS
        elif action == "CHOOSE_OPERATIONS":
            lista_opcoes = op.get("options", [])
            relacao = []
            blocos_filho = []

            # 1 — descobrir filhos diretos de cada opção
            for opt in lista_opcoes:
                sub_ops = opt.get("operations", [])
                filhos = encontrar_escolhas(sub_ops)
                blocos_filho.append(filhos)
                relacao.append(len(filhos))

            # 2 — calcular offsets
            offsets = []
            acumulado = 0
            for count in relacao:
                offsets.append(acumulado)
                acumulado += count

            # 3 — bloco pai
            resultados.append({
                "label": op.get("label", ""),
                "opcoes": [o.get("label", "") for o in lista_opcoes],
                "n": op.get("n"),
                "tam": len(lista_opcoes),
                "relacao": relacao,
                "offsets": offsets
            })

            # 4 — filhos logo abaixo
            for filhos in blocos_filho:
                resultados.extend(filhos)

        # OUTROS ACTIONS CONTINUAM IGUAIS
        if "operations" in op:
            resultados.extend(encontrar_escolhas(op["operations"]))

        if "features" in op:
            for feat in op.get("features", []):
                resultados.extend(encontrar_escolhas(feat.get("operations", [])))

    return resultados

@router_ficha.post("/ficha/")
def criar_ficha_base(dados: CriarFichaRequest):
    """
    Inicializa um novo personagem.
    1. Gera um novo ID baseado nas pastas existentes.
    2. Cria a pasta do personagem.
    3. Salva o character.json inicial com o nome e atributos na lista de 'decisions'.
    """
    
    # Garante que o diretório base de personagens existe
    if not os.path.exists(CHARACTERS_DIR):
        os.makedirs(CHARACTERS_DIR)

    # 1. Encontrar o próximo ID disponível
    # Lista todas as pastas que são números inteiros
    existing_ids = []
    try:
        for nome_pasta in os.listdir(CHARACTERS_DIR):
            caminho_completo = os.path.join(CHARACTERS_DIR, nome_pasta)
            if os.path.isdir(caminho_completo) and nome_pasta.isdigit():
                existing_ids.append(int(nome_pasta))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler banco de dados de personagens: {str(e)}")
    
    next_id = max(existing_ids) + 1 if existing_ids else 0
    
    # 2. Criar o diretório do novo personagem
    character_folder = os.path.join(CHARACTERS_DIR, str(next_id))
    try:
        os.makedirs(character_folder, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar diretório do personagem: {str(e)}")
    
    # 3. Montar a lista de decisões (decisions)
    # IMPORTANTE: A ordem deve bater com a ordem de INPUTs do parser (metadata/character.json)
    # 1º Input: personal.name
    # Loop de Atributos: str, dex, con, int, wis, cha
    decisions = [
        dados.nome,
        dados.atributos.forca,
        dados.atributos.destreza,
        dados.atributos.constituicao,
        dados.atributos.inteligencia,
        dados.atributos.sabedoria,
        dados.atributos.carisma
    ]
    
    character_data = {
        "decisions": decisions
    }
    
    # 4. Salvar o arquivo character.json
    character_file = os.path.join(character_folder, "character.json")
    try:
        with open(character_file, "w", encoding="utf-8") as f:
            json.dump(character_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        # Se falhar ao salvar o arquivo, tenta limpar a pasta criada para não deixar lixo
        os.rmdir(character_folder)
        raise HTTPException(status_code=500, detail=f"Erro ao salvar ficha: {str(e)}")
        
    return {
        "id": next_id,
        "message": "Personagem criado com sucesso!",
        "decisions_saved": decisions
    }

@router_ficha.get("/ficha/classe/{classe}/{nivel}")
def criar_ficha_classe(classe: str, nivel: int):
    dados = carregar_json("classes.json")
    classe_decodificada = unquote(classe)

    if classe_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Classe não encontrada")
    level = f"level_{nivel}"
    if level not in dados[classe_decodificada]:
        raise HTTPException(status_code=400, detail="Nível inválido para a classe")

    bloco = dados[classe_decodificada][level]

    #Pegando todas as operações que seram retornadas para o frontend(usuário ira escolher)
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas

@router_ficha.get("/ficha/raca/{raca}")
def criar_ficha_raca(raca: str):
    dados = carregar_json("races.json")
    raca_decodificada = unquote(raca)

    if raca_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Raça não encontrada")

    bloco = dados[raca_decodificada]

    # Pegando todas as operações que serão retornadas para o frontend
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas

@router_ficha.get("/ficha/subraca/{subraca}")
def criar_ficha_raca(subraca: str):
    dados = carregar_json("subraces.json")
    subraca_decodificada = unquote(subraca)

    if subraca_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Subraça não encontrada")

    bloco = dados[subraca_decodificada]

    # Pegando todas as operações que serão retornadas para o frontend
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas

@router_ficha.get("/ficha/backgrounds/{background}")
def criar_ficha_raca(background: str):
    dados = carregar_json("backgrounds.json")
    background_decodificado = unquote(background)

    if background_decodificado not in dados:
        raise HTTPException(status_code=404, detail="Background não encontrado")

    bloco = dados[background_decodificado]

    #Pegando todas as operações que seram retornadas para o frontend(usuário ira escolher)
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas


if __name__ == "__main__":
    atributos = AtributosInput(forca=15, destreza=14, constituicao=16, inteligencia=12, sabedoria=13, carisma=14)
    criar_ficha_base(CriarFichaRequest(nome="Teste", atributos=atributos))