import json
import re
import math
from typing import List, Dict, Any
from dataclasses import dataclass
from pprint import pprint
# Importa o gdrive atualizado
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

    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        filename = f"{parts[0]}.json"
        
        # Busca arquivo dentro da pasta do módulo (ex: dnd_2014)
        dados = get_file_content(self.token, filename=filename, parent_id=self.folder_id)
        
        if not dados:
            return {}

        for i in range(1, len(parts)):
            if isinstance(dados, dict):
                dados = dados.get(parts[i], {})
            else:
                return {}
                
        return dados if isinstance(dados, dict) else {}

class db_handler(db_homebrew):
    def __init__(self, access_token: str):
        self.token = access_token
        
        # Busca metadata.json na raiz do BD (JSONs_and_Dragons/BD/metadata.json)
        bd_root_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER])
        meta_content = get_file_content(self.token, filename="metadata.json", parent_id=bd_root_id)
        
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

class ImportOperation(Operation):
    query: str
    def run(self):
        # db agora já tem o token via personagem.db
        dados = self.personagem.db.query(self.query)
        novas_ops = dados.get("operations", [])
        if novas_ops:
            self.personagem.ficha.extend(novas_ops)

# ... (InputOperation, SetOperation, ForEachOperation, InitProficiencyOperation permanecem iguais)
class InputOperation(Operation):
    property: str
    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        if not decisions: return
        valor = decisions.pop(0)
        print(f"-> INPUT '{self.property}': {valor}")
        set_nested(self.personagem.data, self.property, valor)

class SetOperation(Operation):
    property: str
    value: Any = None
    formula: str = None
    def run(self):
        if self.formula is not None:
            formula_str = self.formula
            def computed_property(context): return interpolate_and_eval(formula_str, context)
            set_nested(self.personagem.data, self.property, computed_property)
        else:
            set_nested(self.personagem.data, self.property, self.value)

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

# Personagem ========================================================================
class Character:
    def __init__(self, id: int, access_token: str, decisions: List[Any] = None):
        self.id: int = id
        self.access_token = access_token
        
        # Instancia o DB Handler passando o token
        self.db: db_handler = db_handler(self.access_token)

        # Localiza a pasta do personagem: JSONs_and_Dragons/Characters/{id}
        # Isso pode demorar, ideal seria passar o folder_id se já souber
        char_folder_id = ensure_path(self.access_token, [ROOT_FOLDER, CHARACTERS_FOLDER, str(self.id)])
        
        # Tenta carregar character.json
        dados_carregados = get_file_content(self.access_token, filename="character.json", parent_id=char_folder_id)

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
    
    def run_operation(self):
        op_data: Dict[str, Any] = self.ficha[self.n]
        op_args = op_data.copy()
        action = op_args.pop("action", None)

        op_instance = None
        match action:
            case "IMPORT": op_instance = ImportOperation(personagem=self, **op_args)
            case "INPUT": op_instance = InputOperation(personagem=self, **op_args)
            case "SET": op_instance = SetOperation(personagem=self, **op_args)
            case "FOR_EACH": op_instance = ForEachOperation(personagem=self, **op_args)
            case "INIT_PROFICIENCY": op_instance = InitProficiencyOperation(personagem=self, **op_args)
            case _: print(f"Aviso: Ação desconhecida '{action}'")

        if op_instance: op_instance.run()
        self.n += 1

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