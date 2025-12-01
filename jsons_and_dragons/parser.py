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
        # O ID da pasta do módulo é essencial para carregar os JSONs
        self.folder_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER, self.endereço])

    # Lógica para verificar se o valor esperado está na lista
    def _check_in_filter(self, target_value: Any, expected_value: str) -> bool:
        if not target_value:
            return False
            
        # O valor alvo pode ser uma lista (de strings ou objetos)
        if isinstance(target_value, list):
            return any(
                (isinstance(item, dict) and item.get('name') == expected_value) or
                (isinstance(item, str) and item == expected_value)
                for item in target_value
            )
        
        # Caso o alvo seja um valor único (string, int, etc.)
        if isinstance(target_value, str):
            return target_value == expected_value
        
        return False
        
    # Implementa a lógica de filtro complexo para um dicionário de entidades
    def _apply_filter(self, data: Dict[str, Any], filter_str: str) -> Dict[str, Any]:
        
        # 1. Trata operadores AND recursivamente (para encadear filtros)
        if " AND " in filter_str:
            subparts = filter_str.split(" AND ")
            filtered_data = data
            for subpart in subparts:
                filtered_data = self._apply_filter(filtered_data, subpart.strip())
            return filtered_data
            
        # 2. Trata filtro de igualdade (Ex: metadata.type == 'fighting_style')
        elif " == " in filter_str:
            path, expected_value_raw = filter_str.split(" == ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            path = path.strip()
            
            return {
                key: value for key, value in data.items() 
                if str(get_nested(value, path)) == expected_value
            }
        
        # 3. Trata filtro de inclusão (Ex: 'paladin' in metadata.classes)
        elif " in " in filter_str:
            # Formato: 'valor' in path_do_valor
            expected_value_raw, path_raw = filter_str.split(" in ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            path = path_raw.strip()

            return {
                key: value for key, value in data.items() 
                if self._check_in_filter(get_nested(value, path), expected_value)
            }
        
        return data

    # Lida com a aplicação do filtro e a extração do campo de retorno
    def query_parts(self, part: str, dados: Dict[str, Any]) -> Dict[str, Any]:
        
        # Se a parte for um filtro complexo (e.g., com '==', 'in' e opcionalmente '/keys')
        if "==" in part or " in " in part:
            
            # Divide o filtro do campo de retorno (se houver)
            parts = part.rsplit('/', 1)
            filter_only = parts[0]
            return_field = parts[1] if len(parts) > 1 else None

            filtered_data = self._apply_filter(dados, filter_only)
            
            # Se houver campo de retorno, mapeia os resultados
            if return_field == 'keys':
                # Retorna apenas as chaves (nomes das entidades)
                return {key: key for key in filtered_data.keys()}
            
            # Se for um nome de campo específico, retorna o valor desse campo
            if return_field:
                return {key: get_nested(value, return_field.strip()) for key, value in filtered_data.items() if get_nested(value, return_field.strip()) is not None}
                
            return filtered_data
        
        # Se for um nome de campo simples (e.g., 'level_3') ou a chave de uma entidade (e.g., 'Humano')
        return dados.get(part, {})


    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        filename_base = parts[0]
        filename = f"{filename_base}.json"
        
        # 1. Busca o arquivo base dentro da pasta do módulo (self.folder_id)
        current_data = get_file_content(self.token, filename=filename, parent_id=self.folder_id)
        
        if not current_data: 
            # print(f"Erro: Arquivo '{filename}' não encontrado no Drive para o módulo '{self.endereço}'.")
            return {}

        # 2. Itera sobre as partes restantes para filtrar ou acessar aninhadamente
        for i in range(1, len(parts)):
            part = parts[i]
            
            # A função query_parts lida com o acesso aninhado e a lógica de filtro complexo.
            current_data = self.query_parts(part, current_data)
            
            # Se a query_parts retornar um dict vazio, paramos o processamento
            if not current_data and i < len(parts) - 1:
                return {}
        
        return current_data if isinstance(current_data, dict) else {}

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
        n = self.personagem.data.n
        if not decisions: return {
            "label": self.property,
        }
        valor = decisions[n]
        #print(f"-> INPUT '{self.property}': {valor}")
        set_nested(self.personagem.data, self.property, valor)

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
            value = self.value if isinstance(self.value, list) else [self.value]
            set_nested(self.personagem.data, self.property, value)

            
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
    "INCREMENT": IncrementOperation,
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

        while self.n < len(self.data['decisions']):
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