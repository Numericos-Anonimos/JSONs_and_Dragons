import os
import json
from fastapi import APIRouter, HTTPException
from urllib.parse import unquote

#   uvicorn Api.main:app --reload

router_ficha = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
BD_DIR = os.path.join(ROOT_DIR, "BD", "dnd_2014")

def carregar_json(nome_arquivo):
    caminho = os.path.join(BD_DIR, nome_arquivo)
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)



def encontrar_escolhas_antigo(ops):
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
                "relacao": relacao
            })


        # CHOOSE_OPERATIONS
        elif action == "CHOOSE_OPERATIONS":
            lista_opcoes = op.get("options", [])
            relacao = []
            blocos_filho = []

            #1-Conta apenas os filhos diretos daquela opção
            for opt in lista_opcoes:
                sub_ops = opt.get("operations", [])
                filhos = encontrar_escolhas(sub_ops)
                blocos_filho.append(filhos)

                relacao.append(len(filhos))

            #2-Bloco pai
            resultados.append({
                "label": op.get("label", ""),
                "opcoes": [o.get("label","") for o in lista_opcoes],
                "n": op.get("n"),
                "tam": len(lista_opcoes),
                "relacao": relacao
            })

            #3-Filhos logo abaixo
            for filhos in blocos_filho:
                resultados.extend(filhos)
        
        

        if "operations" in op:
            resultados.extend(encontrar_escolhas_antigo(op["operations"]))

        if "features" in op:
            for feat in op.get("features", []):
                resultados.extend(encontrar_escolhas_antigo(feat.get("operations", [])))

    return resultados




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
def criar_ficha_base(nome: str, valores_atributos: dict):
    atributos_esperados = {"Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"}

    if set(valores_atributos.keys()) != atributos_esperados:
        raise HTTPException(
            status_code=400,
            detail=f"Atributos inválidos. Esperado: {atributos_esperados}"
        )

    ficha_base = {
        "characterSheetVersion": "0.2",
        "characterName": nome,
        "currentState": {
            "hitPoints": 0,
            "temporaryHitPoints": 0
        },
        "evolution": [
            {
             "type": "BASE_CHARACTER",
             "operations": [
                    {"action": "SET", "property": "Força_base",        "value": valores_atributos["Força"]},
                    {"action": "SET", "property": "Destreza_base",     "value": valores_atributos["Destreza"]},
                    {"action": "SET", "property": "Constituição_base", "value": valores_atributos["Constituição"]},
                    {"action": "SET", "property": "Inteligência_base", "value": valores_atributos["Inteligência"]},
                    {"action": "SET", "property": "Sabedoria_base",    "value": valores_atributos["Sabedoria"]},
                    {"action": "SET", "property": "Carisma_base",      "value": valores_atributos["Carisma"]}
                ]
            }
        ],
        "inventory": {

        }
    }

    # Essa pasrte vai ser substituida pela integração com o BD no Drive
    return ficha_base






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



@router_ficha.get("/ficha/backgrounds/{background}")
def criar_ficha_raca(background: str):
    dados = carregar_json("backgrounds.json")
    background_decodificada = unquote(background)

    if background_decodificada not in dados:
        raise HTTPException(status_code=404, detail="Classe não encontrada")

    bloco = dados[background_decodificada][background]

    #Pegando todas as operações que seram retornadas para o frontend(usuário ira escolher)
    operacoes = []
    operacoes.extend(bloco.get("operations", []))

    for feat in bloco.get("features", []):
        if "operations" in feat:
            operacoes.extend(feat["operations"])

    escolhas = encontrar_escolhas(operacoes)

    return escolhas







#Teste que retorna os atributos selecionados pelo usuário no formato que vai ser acoplado na ficha
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
