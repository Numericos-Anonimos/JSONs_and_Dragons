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

from Api.gdrive import get_file_content, ensure_path

# Configuração
ROOT_FOLDER = "JSONs_and_Dragons"
DB_FOLDER = "BD"
CHARACTERS_FOLDER = "Characters"

# Utils (Mantidos)
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

# DB Handler (Mantido com a correção do extend)
@dataclass
class db_homebrew: 
    def __init__(self, endereço: str, access_token: str):
        self.endereço = endereço
        self.token = access_token
        self.folder_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER, self.endereço])

    def _check_in_filter(self, target_value: Any, expected_value: str) -> bool:
        if not target_value: return False
        if isinstance(target_value, list):
            return any((isinstance(item, dict) and item.get('name') == expected_value) or (isinstance(item, str) and item == expected_value) for item in target_value)
        if isinstance(target_value, str): return target_value == expected_value
        return False
        
    def _apply_filter(self, data: Dict[str, Any], filter_str: str) -> Dict[str, Any]:
        if filter_str == "keys":
            return {key: key for key in data.keys()}
        elif " AND " in filter_str:
            subparts = filter_str.split(" AND ")
            filtered_data = data
            for subpart in subparts: filtered_data = self._apply_filter(filtered_data, subpart.strip())
            return filtered_data
        elif " == " in filter_str:
            path, expected_value_raw = filter_str.split(" == ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            return {key: value for key, value in data.items() if str(get_nested(value, path.strip())) == expected_value}
        elif " in " in filter_str:
            expected_value_raw, path_raw = filter_str.split(" in ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            return {key: value for key, value in data.items() if self._check_in_filter(get_nested(value, path_raw.strip()), expected_value)}
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
        for endereço in list_endereços: self.db_list.append(db_homebrew(endereço, self.token))

    def query(self, query: str):
        response = {}
        for db in self.db_list:
            resultado_parcial = db.query(query)
            if resultado_parcial:
                if not response:
                    response = resultado_parcial.copy() if isinstance(resultado_parcial, dict) else list(resultado_parcial)
                    continue
                if isinstance(response, dict) and isinstance(resultado_parcial, dict):
                    for k, v in resultado_parcial.items():
                        if k == "operations" and isinstance(v, list) and "operations" in response and isinstance(response["operations"], list):
                            response["operations"].extend(v)
                        else: response[k] = v
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
        
        if n >= len(decisions): 
            return {"label": self.property, "options": None, "type": "input"}
            
        valor = decisions[n]
        set_nested(self.personagem.data, self.property, valor)
        self.personagem.n += 1 
        return 1

class ChooseMapOperation(Operation):
    n: int = 1
    label: str = ""
    options: Any = []
    operations: List[Dict] = []
    
    def _resolve_options(self):
        if isinstance(self.options, list): return self.options
        elif isinstance(self.options, dict) and self.options.get("action") == "REQUEST":
            query = self.options.get("query")
            result = self.personagem.db.query(query)
            if isinstance(result, dict): return list(result.keys())
            return result
        return []

    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        idx = self.personagem.n
        
        if idx >= len(decisions):
            opcoes = self._resolve_options()
            return {"label": self.label, "options": opcoes, "type": "choice", "limit": self.n}

        escolha = decisions[idx]
        itens_escolhidos = escolha if isinstance(escolha, list) else [escolha]
        
        novas_ops = []
        for item in itens_escolhidos:
            for op_template in self.operations:
                op_str = json.dumps(op_template).replace("{THIS}", str(item))
                novas_ops.append(json.loads(op_str))
        
        for op in reversed(novas_ops): self.personagem.ficha.insert(0, op)
        self.personagem.n += 1
        return 1

class ChooseOperationsOperation(Operation):
    n: int = 1
    label: str = ""
    options: list[Dict[str, Any]] = []
    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        idx = self.personagem.n
        labels = [opt.get("label") for opt in self.options]

        if idx >= len(decisions):
            return {"label": self.label, "options": labels, "type": "choice_ops"}

        escolha_label = decisions[idx]
        chosen_opt = next((opt for opt in self.options if opt["label"] == escolha_label), None)
        
        if chosen_opt:
            novas_ops = chosen_opt.get("operations", [])
            for op in reversed(novas_ops): self.personagem.ficha.insert(0, op)
        
        self.personagem.n += 1
        return 1

class SetOperation(Operation):
    property: str
    type: str = "value"
    value: Any = None
    formula: str = None,
    recoversOn: str = "never"

    def run(self):
        if self.type == "value":
            if self.formula is not None:
                formula_str = self.formula
                def computed_property(context): return interpolate_and_eval(formula_str, context)
                set_nested(self.personagem.data, self.property, computed_property)
            else:
                set_nested(self.personagem.data, self.property, self.value)
        elif self.type == "counter":
            _used = f'{self.property}_used'
            _recover = f'{self.property}_recover'
            set_nested(self.personagem.data, _recover, self.recoversOn)
            if self.formula is not None:
                formula_str = self.formula
                def computed_property(context): return interpolate_and_eval(formula_str, context)
                set_nested(self.personagem.data, _used, 0)
                set_nested(self.personagem.data, self.property, computed_property)
            else:
                set_nested(self.personagem.data, _used, 0)
                set_nested(self.personagem.data, self.property, self.value)
        elif self.type == "list":
            pprint(self.personagem.data)
            value = self.value if isinstance(self.value, list) else [self.value]
            set_nested(self.personagem.data, self.property, value)
        return 1
            
class IncrementOperation(Operation):
    property: str
    type: str = ""
    value: int = 1
    formula: str = None
    recoversOn: str = "never"

    def run(self):
        # Se a propriedade existe, pega o type (tem used? ou value é lista)
        if not hasattr(self.personagem.data, self.property):
            # Se não existe, mas tem type, cria a propriedade usando o SET
            if self.type != "":
                op = SetOperation(property=self.property, type=self.type, value=self.value, formula=self.formula, recoversOn=self.recoversOn)
                op.run()
            else: return -1
        else: # Existe
            self.type = getattr(self.personagem.data, self.property).type
            self.recoversOn = getattr(self.personagem.data, self.property).recoversOn
            value = getattr(self.personagem.data, self.property)

            if not callable(value) and self.formula is None:
                value += self.value
                op = SetOperation(personagem=self.personagem, property=self.property, type=self.type, value=value, formula=None, recoversOn=self.recoversOn)
                op.run()
            elif callable(value) and self.formula is None:
                def computed_property(context): return value(context) + self.value
                set_nested(self.personagem.data, self.property, computed_property)
            elif not callable(value) and self.formula is not None:
                formula_str = self.formula
                def computed_property(context): return value + interpolate_and_eval(formula_str, context)
                set_nested(self.personagem.data, self.property, computed_property)
            else: 
                formula_str = self.formula
                def computed_property(context): return value(context) + interpolate_and_eval(formula_str, context)
        return 1

class ImportOperation(Operation):
    query: str
    def run(self):
        entidade = self.personagem.db.query(self.query)
        novas_ops = entidade.get("operations", [])
        if novas_ops: self.personagem.ficha.extend(novas_ops)
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
        
        for op in reversed(novas_ops): self.personagem.ficha.insert(0, op)
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
             for op in reversed(self.operations): self.personagem.ficha.insert(0, op)
        return 1

class GenericPass(Operation):
    def run(self): return 1

operations = {
    "INPUT": InputOperation,
    "SET": SetOperation,
    "INCREMENT": IncrementOperation,
    "CHOOSE_MAP": ChooseMapOperation,
    "CHOOSE_OPERATIONS": ChooseOperationsOperation,
    "REQUEST": GenericPass, # REQUEST puro não faz nada no run, só dentro do Choose
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
        
        self.data = {
            "decisions": decisions if decisions else [],
            "state": {"hp": 0},
            "proficiencies": [],
            "attributes": {}, 
            "properties": {},
            "personal": {}
        }
        self.n = 0 # Ponteiro de decisões
        self.ficha = [{"action": "IMPORT", "query": "metadata/character"}]
        self.required_decision = None

        print(f"--- Iniciando processamento Character ID {id} ---")
        self.process_queue()

    def add_race(self, race: str):
        print(f"\n-> Adicionando Raça: {race}")
        self.ficha.append({"action": "IMPORT", "query": f"races/{race}"})
        # Reset da decisão requerida caso estivesse travado antes, pois agora temos uma nova ação
        self.required_decision = None 
        self.process_queue()

    def process_queue(self):
        self.required_decision = None
        while len(self.ficha) > 0:
            # Check de segurança para não processar se já estivermos esperando uma decisão
            if self.required_decision:
                print(f"(!) Processamento pausado. Aguardando: {self.required_decision['label']}")
                break

            result = self.run_operation()
            
            if isinstance(result, dict):
                self.required_decision = result
                print(f"(!) Decisão Necessária detectada: {result['label']}")
                break 
            
            if result == -1:
                print("(X) Erro fatal na operação.")
                break
        
        if not self.ficha and not self.required_decision:
            print("(v) Fila vazia. Processamento concluído.")

    def run_operation(self):
        if not self.ficha: return 1
        
        op_data = self.ficha.pop(0)
        op_args = op_data.copy()
        action = op_args.pop("action", None)
        
        # Debug detalhado
        param = op_args.get('property') or op_args.get('label') or op_args.get('query') or op_args.get('name') or ''
        print(f"[N={self.n}] Exec: {action} - {param}")

        op_class = operations.get(action)
        if not op_class: 
            print(f"AVISO: Operação '{action}' não implementada.")
            return 1
        
        op_instance = op_class(personagem=self, **op_args)
        result = op_instance.run()
        
        if isinstance(result, dict):
            # Devolve para o topo da fila
            print(f"    -> Pausando em {action} (Falta decisão {self.n})")
            self.ficha.insert(0, op_data)
            
        return result

    def get_stat(self, path: str) -> Any:
        return resolve_value(get_nested(self.data, path), self.data)

# Main =======================================================
def main():
    env_token = os.getenv("JWT_TOKEN")
    env_secret = os.getenv("JWT_SECRET")
    payload = jwt.decode(env_token, env_secret, algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
    google_access_token = payload.get("google_access_token")

    # MOCK 1: Apenas Nome e Atributos. SEM RAÇA.
    decisoes_parciais = [
        "Tony Starforge",    
        15, 12, 14, 8, 8, 14,
        "Anão"
    ]
    
    print("\n--- TESTE 1: Inicialização ---")
    personagem = Character(0, access_token=google_access_token, decisions=decisoes_parciais)
    
    # Aqui o processamento deve terminar com a fila vazia (pois metadata/character foi todo resolvido)
    
    print("\n--- TESTE 2: Adicionando Raça (Deve Pausar) ---")
    personagem.add_race("Humano")
    
    # Esperado: Pausar em "Idioma Adicional"
    if personagem.required_decision:
        print(f"\n>> JSON RETORNO: {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}")
    else:
        print("\n>> ERRO: Não pausou onde deveria!")
    pprint(personagem.data)

    print("\n--- TESTE 3: Retomada (Com Subraça) ---")
    # Simulando o Frontend mandando tudo de novo + a nova escolha
    personagem.data["decisions"] += ["Humano (Variante)"]
    personagem.process_queue()
    pprint(personagem.data)
    
    # Esperado: Pausar em "Subraça"
    if personagem.required_decision:
        print(f"\n>> JSON RETORNO (Passo 2): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}")
        print(f"Decisões consumidas: {personagem.n} de {len(personagem.data['decisions'])}")

if __name__ == "__main__":
    main()