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
        # Cache simples do ID da pasta para não buscar toda vez
        self.folder_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER, self.endereço])

    def query_parts(self, part: str, dados: Dict[str, Any]) -> Dict[str, Any]:
        if "AND" in part:
            subparts = part.split("AND")
            for subpart in subparts:
                dados = self.query_parts(subpart, dados)
        elif "=" in part: # Preciso de uma operação em todos os itens:
            pass
        elif "in" in part: # Preciso de uma operação em todos os itens:
            pass
        else:
            dados = dados.get(part, {})
        return dados        

    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        filename = f"{parts[0]}.json"
        
        # Busca arquivo dentro da pasta do módulo (ex: dnd_2014)
        dados = get_file_content(self.token, filename=filename, parent_id=self.folder_id)
        
        if not dados:
            return {}

        for i in range(1, len(parts)):
            if isinstance(dados, dict):
                dados = self.query_parts(parts[i], dados)
            else:
                return {}
                
        return dados if isinstance(dados, dict) else {}

class db_handler(db_homebrew):
    def __init__(self, access_token: str):
        self.token = access_token
        
        # Busca metadata.json na raiz do BD (JSONs_and_Dragons/BD/metadata.json)
        bd_root_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER])
        print(f"aaaaaaaa {bd_root_id}")
        meta_content = get_file_content(self.token, filename="metadata.json", parent_id=bd_root_id)
        print(f"bbbbbbbb {meta_content}")
        
        list_endereços = []
        if meta_content:
            list_endereços = meta_content.get('modules', [])

        self.db_list = []
        for endereço in list_endereços:
            # Instancia db_homebrew passando o token
            self.db_list.append(db_homebrew(endereço, self.token))

    # O init do db_homebrew original não era chamado aqui, corrigido para loop acima
    def query(self, query: str):
        response = {}
        for db in self.db_list:
            resultado_parcial = db.query(query)
            if query == "races/Humano":
                print(f"ccccccc {resultado_parcial}")
            for key, value in resultado_parcial.items():
                if key not in response:
                    response[key] = value
                else:
                    if isinstance(response[key], list) and isinstance(value, list):
                        response[key].extend(value)
                    elif isinstance(response[key], dict) and isinstance(value, dict):
                        response[key].update(value)
                    else:
                        response[key] = value
        return response

# Operações (Operation, ImportOperation, etc - Mantidas iguais, apenas ImportOperation ajustada)
@dataclass
class Operation:
    def __init__(self, **kwargs: dict[str, Any]):
        if "personagem" in kwargs:
            self.personagem: 'Character' = kwargs.pop("personagem")
        for key, value in kwargs.items():
            setattr(self, key, value)
    def run(self): pass

class InputOperation(Operation):
    property: str

    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        if not decisions: return
        valor = decisions.pop(0)
        #print(f"-> INPUT '{self.property}': {valor}")
        set_nested(self.personagem.data, self.property, valor)

class SetOperation(Operation):
    property: str
    type: str = "value"
    value: Any = None
    formula: str = None,
    recoversOn: str = "never"

    def run(self):
        if self.formula is not None:
            formula_str = self.formula
            def computed_property(context): return interpolate_and_eval(formula_str, context)
            set_nested(self.personagem.data, self.property, computed_property)
        else:
            set_nested(self.personagem.data, self.property, self.value)

class ChooseMapOperation(Operation):
    n: int = 1
    label: str = ""
    options: Union[List[str], Dict[str, Any]] = []
    operations: List[Dict]
    
    def run(self):
        pass

class ChooseOperationsOperation(Operation):
    n: int = 1
    label: str = ""
    options: list[Dict[str, Any]] = []

    def run(self):
        pass

class RequestOperation(Operation):
    query: str
    
    def run(self):
        pass

class ImportOperation(Operation):
    query: str
    
    def run(self):
        # db agora já tem o token via personagem.db
        dados = self.personagem.db.query(self.query)
        novas_ops = dados.get("operations", [])
        if novas_ops:
            self.personagem.ficha.extend(novas_ops)
        print(f"\n{novas_ops}")

class ForEachOperation(Operation):
    list: List[str]
    operations: List[Dict]

    def run(self):
        items = self.list
        if isinstance(items, str):
            items = interpolate_and_eval(items, self.personagem.data)
            if not isinstance(items, list): items = []
        expanded_ops = []
        for item in items:
            for op_template in self.operations:
                op_str = json.dumps(op_template)
                op_str = op_str.replace("{THIS}", str(item))
                new_op = json.loads(op_str)
                expanded_ops.append(new_op)
        for op in reversed(expanded_ops):
            self.personagem.ficha.insert(self.personagem.n + 1, op)

class InitProficiencyOperation(Operation):
    category: str
    name: str
    attributes: str = None
    multiplier: int = 0
    def run(self):
        nome_resolvido = interpolate_and_eval(self.name, self.personagem.data)
        prof_entry = {"name": nome_resolvido, "category": self.category, "multiplier": self.multiplier}
        if self.attributes: prof_entry["attribute"] = self.attributes
        current_profs = self.personagem.data.get("proficiencies", [])
        current_profs.append(prof_entry)
        self.personagem.data["proficiencies"] = current_profs

class AddItemOperation(Operation):
    name: str
    query: str
    amount: int = 1
    
    def run(self):
        pass

class AddSpellcastingOperation(Operation):
    name: str
    can_multiclass: bool = False
    multiclass_formula: str = ""
    spellcastig_modifier: str = ""
    spell_save_dc: str = ""
    spell_attack_modifier: str = ""
    spells_prepared: str = ""
    spells_known: str = ""
    spellSlotsRecoverOn: str = ""
    spellbook_query: str = ""
    spellSlots: list[list[int]] = [[0, 0, 0, 0, 0, 0, 0, 0, 0]]
    
    def run(self):
        pass

class AddSpellOperation(Operation):
    name: str
    type: str
    spellbook: str
   
    def run(self):
        pass

class AddActionOperation(Operation):
    name: str
    cost: list[dict[str, Any]] = []

    def run(self):
        pass

class AddFeatureOperation(Operation):
    name: str
    description: str
    operations: list[dict[str, Any]] = []

    def run(self):
        pass

operations = {
    "INPUT": InputOperation,
    "SET": SetOperation,
    "CHOOSE_MAP": ChooseMapOperation,
    "CHOOSE_OPERATIONS": ChooseOperationsOperation,
    "REQUEST": RequestOperation,
    "IMPORT": ImportOperation,
    "FOR_EACH": ForEachOperation,
    "INIT_PROFICIENCY": InitProficiencyOperation,
    "ADD_ITEM": AddItemOperation,
    "ADD_SPELLCASTING": AddSpellcastingOperation,
    "ADD_SPELL": AddSpellOperation,
    "ADD_ACTION": AddActionOperation,
    "ADD_FEATURE": AddFeatureOperation,
}

# Personagem ========================================================================
class Character:
    def __init__(self, id: int, access_token: str, decisions: List[Any] = None):
        self.id: int = id
        self.access_token = access_token
        
        self.db: db_handler = db_handler(self.access_token)
        char_folder_id = ensure_path(self.access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(self.id)])
        print(f"ccccccc {char_folder_id}")
        dados_carregados = get_file_content(self.access_token, filename="character.json", parent_id=char_folder_id)
        print(f"ddddddd {dados_carregados}")

        if dados_carregados:
            self.data: Dict[str, Any] = dados_carregados
        else:
            self.data: Dict[str, Any] = {
                "decisions": decisions if decisions else [],
                "state": {"hp": 0},
                "proficiencies": [],
                "attributes": {}, 
                "properties": {},
                "personal": {}
            }

        self.n: int = 0
        self.ficha: list[Dict[str, Any]] = [
            {"action": "IMPORT", "query": "metadata/character"}
        ]

        print(f"--- Iniciando processamento Character ID {id} ---")
        while self.n < len(self.ficha):
            self.run_operation()

    def add_race(self, race: str):
        self.ficha.append(
            {"action": "IMPORT", "query": f"races/{race}"}
        )

        while self.n < len(self.ficha):
            resp = self.run_operation()
            if resp != -1:
                return resp
        return resp

    def run_operation(self):
        op_data: Dict[str, Any] = self.ficha[self.n]
        op_args = op_data.copy()
        action = op_args.pop("action", None)

        global operations
        op_instance = operations.get(action, None)
        if not op_instance:
            print(f"Aviso: Ação desconhecida '{action}'")
            return -1
        op_instance = op_instance(personagem=self, **op_args)

        resp = op_instance.run()
        self.n += 1
        return resp

    def get_stat(self, path: str) -> Any:
        raw = get_nested(self.data, path)
        return resolve_value(raw, self.data)

    def export_data(self) -> Dict:
        def resolve_recursive(d):
            if isinstance(d, dict): return {k: resolve_recursive(v) for k, v in d.items()}
            elif isinstance(d, list): return [resolve_recursive(v) for v in d]
            elif callable(d): return d(self.data)
            else: return d
        return resolve_recursive(self.data)

# Main para Testes Independentes =======================================================
def main():
    env_token = os.getenv("JWT_TOKEN")
    env_secret = os.getenv("JWT_SECRET")
    payload = jwt.decode(env_token, env_secret, algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
    google_access_token = payload.get("google_access_token")


    decisoes_mock = [
        "Tony Starforge",    # nome
        15, 12, 14, 8, 8, 14 # atributos
    ]
    personagem = Character(0, access_token=google_access_token, decisions=decisoes_mock)
    #print(personagem.data)
   
    """print("\n=== Teste de Reatividade ===")
    str_mod_original = personagem.get_stat("attributes.str.modifier")
    print(f"Modificador de Força (Score 15): {str_mod_original}")

    print("-> Aumentando Força para 18...")
    personagem.data['attributes']['str']['score'] = 18

    str_mod_novo = personagem.get_stat("attributes.str.modifier")
    str_save_novo = personagem.get_stat("attributes.str.save")
    
    print(f"Modificador de Força (Score 18): {str_mod_novo}")
    print(f"Save de Força (Baseado no mod): {str_save_novo}")

    pprint(personagem.data)"""

    personagem.add_race("Humano")


if __name__ == "__main__":
    main()