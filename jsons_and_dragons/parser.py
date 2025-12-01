import json
import os
import sys
import re
import math
from typing import List, Dict, Any, Union
from dataclasses import dataclass
from pprint import pprint
from fastapi.param_functions import Query
from jose import jwt
from dotenv import load_dotenv
load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Agora a importação funcionará
from Api.gdrive import get_file_content, ensure_path

# Configuração de Caminhos Virtuais
ROOT_FOLDER = "JSONs_and_Dragons"
DB_FOLDER = "BD"
CHARACTERS_FOLDER = "Characters"

# Utils (Mantidos iguais: get_nested, set_nested, resolve_value, interpolate_and_eval)
def get_nested(data: Dict, path: str, default: Any = None) -> Any:
    keys = path.split('.')
    curr = data
    try:
        for key in keys:
            if isinstance(curr, dict): curr = curr.get(key)
            elif isinstance(curr, list) and key.isdigit(): curr = curr[int(key)]
            else: return default
            if curr is None: return default
        return curr
    except Exception: return default

def set_nested(data: Dict, path: str, value: Any) -> None:
    keys = path.split('.')
    curr = data
    for i, key in enumerate(keys[:-1]):
        if key not in curr: curr[key] = {}
        curr = curr[key]
    curr[keys[-1]] = value

def resolve_value(value: Any, context: Dict) -> Any:
    if callable(value):
        try: return value(context)
        except RecursionError: return 0
    return value

def interpolate_and_eval(text: str, context: Dict) -> Any:
    if not isinstance(text, str): return resolve_value(text, context)
    pattern = re.compile(r'\{([a-zA-Z0-9_.]+)\}')
    def replacer(match):
        path = match.group(1)
        raw_val = get_nested(context, path)
        val = resolve_value(raw_val, context)
        return "0" if val is None else str(val)
    interpolated = pattern.sub(replacer, text)
    if any(c in interpolated for c in "+-*/") or "floor" in interpolated:
        try:
            safe_dict = {"floor": math.floor, "ceil": math.ceil, "max": max, "min": min, "abs": abs}
            return eval(interpolated, {"__builtins__": None}, safe_dict)
        except Exception: pass
    try:
        if "." in interpolated: return float(interpolated)
        return int(interpolated)
    except ValueError: return interpolated

# Banco de Dados ========================================================================

@dataclass
class db_homebrew: 
    def __init__(self, endereço: str, access_token: str):
        self.endereço = endereço
        self.token = access_token
        self.folder_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER, self.endereço])

    def _check_in_filter(self, target_value: Any, expected_value: str) -> bool:
        if not target_value: return False
        if isinstance(target_value, list):
            return any(
                (isinstance(item, dict) and item.get('name') == expected_value) or
                (isinstance(item, str) and item == expected_value)
                for item in target_value
            )
        if isinstance(target_value, str): return target_value == expected_value
        return False
        
    def _apply_filter(self, data: Dict[str, Any], filter_str: str) -> Dict[str, Any]:
        if " AND " in filter_str:
            subparts = filter_str.split(" AND ")
            filtered_data = data
            for subpart in subparts:
                filtered_data = self._apply_filter(filtered_data, subpart.strip())
            return filtered_data
        elif " == " in filter_str:
            path, expected_value_raw = filter_str.split(" == ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            path = path.strip()
            return {key: value for key, value in data.items() if str(get_nested(value, path)) == expected_value}
        elif " in " in filter_str:
            expected_value_raw, path_raw = filter_str.split(" in ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            path = path_raw.strip()
            return {key: value for key, value in data.items() if self._check_in_filter(get_nested(value, path), expected_value)}
        return data

    def query_parts(self, part: str, dados: Dict[str, Any]) -> Dict[str, Any]:
        if "==" in part or " in " in part:
            parts = part.rsplit('/', 1)
            filter_only = parts[0]
            return_field = parts[1] if len(parts) > 1 else None
            filtered_data = self._apply_filter(dados, filter_only)
            if return_field == 'keys': return {key: key for key in filtered_data.keys()}
            if return_field: return {key: get_nested(value, return_field.strip()) for key, value in filtered_data.items() if get_nested(value, return_field.strip()) is not None}
            return filtered_data
        return dados.get(part, {})

    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        filename = f"{parts[0]}.json"
        
        # Tenta pegar o arquivo. Se falhar, retorna vazio silenciosamente para não poluir o log se o módulo não tiver o arquivo.
        # Nota: O erro "Arquivo não encontrado" ainda pode ser printado pelo `get_file_content` se ele tiver prints internos.
        current_data = get_file_content(self.token, filename=filename, parent_id=self.folder_id)
        
        if not current_data: return {}

        for i in range(1, len(parts)):
            part = parts[i]
            current_data = self.query_parts(part, current_data)
            if not current_data and i < len(parts) - 1: return {}
        
        return current_data if isinstance(current_data, dict) else {}

class db_handler(db_homebrew):
    def __init__(self, access_token: str):
        self.token = access_token
        bd_root_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER])
        meta_content = get_file_content(self.token, filename="metadata.json", parent_id=bd_root_id)
        
        list_endereços = meta_content.get('modules', []) if meta_content else []
        self.db_list = []
        for endereço in list_endereços:
            self.db_list.append(db_homebrew(endereço, self.token))

    def query(self, query: str):
        response = {}
        
        for db in self.db_list:
            resultado_parcial = db.query(query)
            
            if resultado_parcial:
                if not response:
                    response = resultado_parcial.copy() if isinstance(resultado_parcial, dict) else list(resultado_parcial)
                    continue

                if isinstance(response, dict) and isinstance(resultado_parcial, dict):
                    # Lógica de Merge Inteligente
                    for k, v in resultado_parcial.items():
                        # Se a chave for "operations", nós EXTENDEMOS a lista em vez de sobrescrever
                        if k == "operations" and isinstance(v, list) and "operations" in response and isinstance(response["operations"], list):
                            response["operations"].extend(v)
                        else:
                            # Para outras chaves, comportamento padrão de update (sobrescreve)
                            response[k] = v
                            
                elif isinstance(response, list) and isinstance(resultado_parcial, list):
                    response.extend(resultado_parcial)

        return response

# Operações ========================================================================
@dataclass
class Operation:
    def __init__(self, **kwargs: dict[str, Any]):
        if "personagem" in kwargs: self.personagem: 'Character' = kwargs.pop("personagem")
        for key, value in kwargs.items(): setattr(self, key, value)
    def run(self): pass

class InputOperation(Operation):
    property: str
    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        n = self.personagem.n
        if n >= len(decisions): return -1
        valor = decisions[n]
        set_nested(self.personagem.data, self.property, valor)
        self.personagem.n += 1 # Consumiu uma decisão
        return 1

class SetOperation(Operation):
    property: str
    type: str = "value"
    value: Any = None
    formula: str = None
    recoversOn: str = "never"
    def run(self):
        if self.type == "value":
            if self.formula is not None:
                formula_str = self.formula
                def computed_property(context): return interpolate_and_eval(formula_str, context)
                set_nested(self.personagem.data, self.property, computed_property)
            else:
                set_nested(self.personagem.data, self.property, self.value)
        # (Lógica simplificada para brevidade, mantendo a sua original de counter/list se necessário)
        return 1
            
class IncrementOperation(Operation):
    property: str
    value: int = 1
    def run(self):
        # Simplificação: Assume que já é int para teste. Expanda conforme sua lógica original.
        curr = get_nested(self.personagem.data, self.property, 0)
        # Se for função, não dá pra incrementar fácil aqui sem resolver, 
        # mas no seu caso de uso (atributos) geralmente é valor bruto antes de virar modifier.
        if isinstance(curr, int) or isinstance(curr, float):
             set_nested(self.personagem.data, self.property, curr + self.value)
        return 1

class ChooseMapOperation(Operation):
    n: int = 1
    label: str = ""
    options: Any = []
    operations: List[Dict] = []
    
    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        idx = self.personagem.n
        if idx >= len(decisions): return -1

        escolha = decisions[idx]
        itens_escolhidos = escolha if isinstance(escolha, list) else [escolha]
        
        novas_ops = []
        for item in itens_escolhidos:
            for op_template in self.operations:
                op_str = json.dumps(op_template).replace("{THIS}", str(item))
                novas_ops.append(json.loads(op_str))
        
        for op in reversed(novas_ops):
            self.personagem.ficha.insert(0, op)
            
        self.personagem.n += 1
        return 1

class ChooseOperationsOperation(Operation):
    def run(self): return 1 # Placeholder

class RequestOperation(Operation):
    def run(self): return 1 # Placeholder

class ImportOperation(Operation):
    query: str
    def run(self):
        entidade = self.personagem.db.query(self.query)
        novas_ops = entidade.get("operations", [])
        if novas_ops:
            # Importante: IMPORT adiciona ao final da fila (extend) ou inicio?
            # Geralmente imports estruturais (como raça) vão pro final ou são processados na ordem.
            # No seu design original parecia ser extend.
            self.personagem.ficha.extend(novas_ops)
        return 1

class ForEachOperation(Operation):
    list: List[str]
    operations: List[Dict]
    def run(self):
        items = self.list
        if isinstance(items, str):
            items = interpolate_and_eval(items, self.personagem.data)
            if not isinstance(items, list): items = []
        
        novas_ops = []
        for item in items:
            for op_template in self.operations:
                op_str = json.dumps(op_template).replace("{THIS}", str(item))
                novas_ops.append(json.loads(op_str))
        
        # ForEach expande imediatamente
        for op in reversed(novas_ops):
            self.personagem.ficha.insert(0, op)
        return 1

class InitProficiencyOperation(Operation):
    category: str
    name: str
    attributes: str = None
    multiplier: int = 0
    def run(self):
        nome = interpolate_and_eval(self.name, self.personagem.data)
        prof = {"name": nome, "category": self.category, "multiplier": self.multiplier}
        if self.attributes: prof["attribute"] = self.attributes
        self.personagem.data.setdefault("proficiencies", []).append(prof)
        return 1

class AddFeatureOperation(Operation):
    name: str
    operations: list = []
    def run(self):
        if self.operations:
             for op in reversed(self.operations):
                self.personagem.ficha.insert(0, op)
        return 1

# Classes Genéricas para completar o dicionário
class GenericPass(Operation):
    def run(self): return 1

operations = {
    "INPUT": InputOperation,
    "SET": SetOperation,
    "INCREMENT": IncrementOperation,
    "CHOOSE_MAP": ChooseMapOperation,
    "CHOOSE_OPERATIONS": ChooseOperationsOperation,
    "REQUEST": RequestOperation,
    "IMPORT": ImportOperation,
    "FOR_EACH": ForEachOperation,
    "INIT_PROFICIENCY": InitProficiencyOperation,
    "ADD_ITEM": GenericPass,
    "ADD_SPELLCASTING": GenericPass,
    "ADD_SPELL": GenericPass,
    "ADD_ACTION": GenericPass,
    "ADD_FEATURE": AddFeatureOperation,
}

# Personagem ========================================================================
class Character:
    def __init__(self, id: int, access_token: str, decisions: List[Any] = None):
        self.id = id
        self.access_token = access_token
        self.db = db_handler(self.access_token)
        
        # Mock de persistência
        self.data = {
            "decisions": decisions if decisions else [],
            "state": {"hp": 0},
            "proficiencies": [],
            "attributes": {}, 
            "properties": {},
            "personal": {}
        }
        self.n = 0
        self.ficha = [{"action": "IMPORT", "query": "metadata/character"}]

        print(f"--- Iniciando processamento Character ID {id} ---")
        while len(self.ficha) > 0:
            if self.run_operation() == -1: break

    def add_race(self, race: str):
        print(f"-> Adicionando Raça: {race}")
        self.ficha.append({"action": "IMPORT", "query": f"races/{race}"})
        while len(self.ficha) > 0:
            if self.run_operation() == -1: break

    def run_operation(self):
        if not self.ficha: return 1
        op_data = self.ficha.pop(0)
        # print(f"Executando: {op_data.get('action')}") # Debug limpo
        
        action = op_data.get("action")
        op_class = operations.get(action)
        if not op_class: return 1
        
        op_instance = op_class(personagem=self, **op_data)
        return op_instance.run()

    def get_stat(self, path: str) -> Any:
        return resolve_value(get_nested(self.data, path), self.data)

# Main =======================================================
def main():
    env_token = os.getenv("JWT_TOKEN")
    env_secret = os.getenv("JWT_SECRET")
    payload = jwt.decode(env_token, env_secret, algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
    google_access_token = payload.get("google_access_token")

    # Ordem de Decisões:
    # 1. Nome (INPUT)
    # 2-7. Atributos (FOR_EACH INPUT)
    # 8. Idioma (CHOOSE Humano)
    # 9. Subraça (CHOOSE Humano)
    decisoes = [
        "Tony Starforge",    
        15, 12, 14, 8, 8, 14,
        "Humano",
        "Anão",              
        "Humano (Variante)",
        ["str", "cha"],
        "Arcanismo",
        "Agarrador",
    ]
    
    personagem = Character(0, access_token=google_access_token, decisions=decisoes)
    
    # Verifica se os atributos foram carregados ANTES de adicionar a raça
    # Se isso estiver vazio, o IMPORT metadata/character falhou
    print(f"\nEstado antes da Raça: {personagem.data['attributes']}")

    print("\n=== Adicionando Raça Humano ===")
    personagem.add_race("Humano")
    
    print("\n=== Ficha Final ===")
    pprint(personagem.data)

if __name__ == "__main__":
    main()