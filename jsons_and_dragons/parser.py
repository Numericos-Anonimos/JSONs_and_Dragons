import json
import os
import sys
import re
import math
from typing import List, Dict, Any, Union
from pprint import pprint
from jose import jwt
import dill as pickle # Usamos dill para conseguir salvar as lambdas/funções
import base64
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

# Utils (Originais)
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
        if " AND " in filter_str:
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
        
        # Silencia erro de arquivo não encontrado na API se não existir
        # (Assumindo que get_file_content já trata e retorna None)
        current_data = get_file_content(self.token, filename=filename, parent_id=self.folder_id)
        if not current_data: return {}
        
        for i in range(1, len(parts)):
            part = parts[i]
            if part == "keys": return list(current_data.keys())
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
                        # Lógica de merge para não perder operações
                        if k == "operations" and isinstance(v, list) and "operations" in response and isinstance(response["operations"], list):
                            response["operations"].extend(v)
                        else: response[k] = v
                elif isinstance(response, list) and isinstance(resultado_parcial, list):
                    response.extend(resultado_parcial)
        return response

# Operações ========================================================================

# Removido @dataclass para evitar conflito com __init__ customizado e herança
class Operation:
    def __init__(self, **kwargs: dict[str, Any]):
        if "personagem" in kwargs: 
            self.personagem: 'Character' = kwargs.pop("personagem")
        for key, value in kwargs.items(): 
            setattr(self, key, value)
            
    def run(self): pass

# --- OPERAÇÕES QUE PAUSAM ---

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
        #print(f"zzzzzz {self.options}")
        if isinstance(self.options, list): return self.options
        elif isinstance(self.options, dict) and self.options.get("action") == "REQUEST":
            #print(f"zzzzzz {self.options}")
            query = self.options.get("query")
            result = self.personagem.db.query(query)
            if isinstance(result, dict): return list(result.keys())
            #print(f"yyyyyy {result}")
            return result
        return []

    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        idx = self.personagem.n
        
        if idx >= len(decisions):
            #print(f"zzzzzz {self.options}")
            opcoes = self._resolve_options()
            return {
                "label": self.label, 
                "options": opcoes, 
                "n": self.n
            }

        escolha = decisions[idx]
        # Se n > 1, espera-se que a escolha seja uma lista de n itens
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
        options = [opt.get("label") for opt in self.options]

        if idx >= len(decisions):
            return {
                "label": self.label, 
                "options": options, 
                "n": self.n
            }

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
            # Lógica de lista corrigida: append/extend seguro
            current_val = get_nested(self.personagem.data, self.property)
            lista_atual = current_val if isinstance(current_val, list) else []
            novos_valores = self.value if isinstance(self.value, list) else [self.value]
            lista_atual.extend(novos_valores)
            set_nested(self.personagem.data, self.property, lista_atual)
        
        return 1
            
class IncrementOperation(Operation):
    property: str
    type: str = ""
    value: int = 1
    formula: str = None
    recoversOn: str = "never"

    def run(self):
        # 1. Busca o valor atual de forma segura
        curr_obj = get_nested(self.personagem.data, self.property)
        
        # 2. Se não existe, cria (delegando para SetOperation)
        if curr_obj is None:
            # Se não tem tipo definido, assume valor simples (0) + incremento
            if self.type == "": 
                # Caso de uso: incremento de valor bruto que não existia (ex: atributos se não iniciados)
                set_nested(self.personagem.data, self.property, self.value)
            else:
                # Caso de uso: criar lista ou counter
                op = SetOperation(
                    personagem=self.personagem,
                    property=self.property, type=self.type, value=self.value, formula=self.formula, recoversOn=self.recoversOn
                )
                op.run()
        else:
            # 3. Se existe, incrementa
            if not callable(curr_obj) and self.formula is None:
                if isinstance(curr_obj, (int, float)):
                    new_val = curr_obj + self.value
                    set_nested(self.personagem.data, self.property, new_val)
                elif isinstance(curr_obj, list):
                    # Incremento em lista = adicionar item
                    op = SetOperation(personagem=self.personagem, property=self.property, type="list", value=self.value)
                    op.run()
                    
            elif callable(curr_obj) and self.formula is None:
                def computed_property(context): return curr_obj(context) + self.value
                set_nested(self.personagem.data, self.property, computed_property)
                
            elif not callable(curr_obj) and self.formula is not None:
                formula_str = self.formula
                def computed_property(context): return curr_obj + interpolate_and_eval(formula_str, context)
                set_nested(self.personagem.data, self.property, computed_property)
            else: 
                formula_str = self.formula
                def computed_property(context): return curr_obj(context) + interpolate_and_eval(formula_str, context)
                set_nested(self.personagem.data, self.property, computed_property)
                
        return 1

class InitOperation(SetOperation):
    def run(self):
        if get_nested(self.personagem.data, self.property) is None:
            super().run()
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
    roll: str = "N"

    def run(self):
        nome = interpolate_and_eval(self.name, self.personagem.data)
        path = f"proficiency.{self.category}.{nome}"
        
        prof_data = {
            "attribute": self.attributes,
            "multiplier": self.multiplier,
            "roll": self.roll
        }
        set_nested(self.personagem.data, path, prof_data)
        
        cat_cap = self.category
        name_cap = nome

        # Função reativa para calcular o bônus
        def computed_bonus(context):
            # 1. Recupera o objeto da perícia atual do contexto (para pegar multiplier atualizado)
            p_data = get_nested(context, f"proficiency.{cat_cap}.{name_cap}")
            if not p_data: return 0
            
            # 2. Descobre qual atributo usar e qual o multiplicador atual
            attr_key = p_data.get("attribute")
            mult = p_data.get("multiplier", 0)
            
            # 3. Busca o modificador do atributo (resolvendo recursivamente se for função)
            attr_mod = 0
            if attr_key:
                raw_mod = get_nested(context, f"attributes.{attr_key}.modifier")
                attr_mod = resolve_value(raw_mod, context)
            
            # 4. Busca o bônus de proficiência global
            pb = resolve_value(get_nested(context, "properties.proficiency"), context)
            
            # 5. Calcula: Mod + (PB * Multiplier)
            try:
                return int(int(attr_mod) + (int(pb) * float(mult)))
            except (ValueError, TypeError):
                return 0

        # Salva a função de bônus no caminho .bonus
        set_nested(self.personagem.data, f"{path}.bonus", computed_bonus)
        
        return 1

class AddItemOperation(Operation):
    name: str = None
    query: str
    amount: int = 1
    
    def run(self):
        # 1. Busca o item no Banco de Dados
        # A query geralmente retorna um dict { "NomeDoItem": { ...dados... } }
        result = self.personagem.db.query(self.query)
        
        if not result:
            print(f"(X) Item não encontrado para query: {self.query}")
            return 1

        # Resolve o nome real e o conteúdo
        item_key = list(result.keys())[0]
        item_data = result[item_key]

        # 2. Define o nome de exibição (Nickname ou Original)
        display_name = self.name if self.name else item_key

        # 3. Adiciona ao Inventário
        # Verifica se já existe para somar a quantidade
        path = f"inventory.{display_name}"
        existing_item = get_nested(self.personagem.data, path)
        
        final_amount = self.amount
        if existing_item:
            final_amount += existing_item.get("amount", 0)
        
        # Cria a cópia do item para o inventário
        inventory_item = item_data.copy()
        inventory_item["amount"] = final_amount
        # Limpa operações do item salvo no inventário para não duplicar lógica ao salvar o JSON do char
        if "operations" in inventory_item:
            del inventory_item["operations"]

        set_nested(self.personagem.data, path, inventory_item)

        # 4. Injeta as Operações do Item na Fila (ex: Armadura mudando CA)
        # Itens podem ter operações passivas que devem rodar ao serem adquiridos
        if "operations" in item_data:
            ops = item_data["operations"]
            # Inserimos no início da fila (ordem reversa) para execução imediata
            for op in reversed(ops):
                self.personagem.ficha.insert(0, op)

        return 1

class AddSpellcastingOperation(Operation):
    name: str
    can_multiclass: bool = False
    multiclass_formula: str = ""
    spellcasting_modifier: str = "" # Note: typo 'spellcastig' in some jsons, supporting standard
    spell_save_dc: str = ""
    spell_attack_modifier: str = ""
    spells_prepared: str = ""
    spells_known: str = ""
    spellSlotsRecoverOn: str = ""
    spellbook_query: str = ""
    spellSlots: list[list[int]] = [[0, 0, 0, 0, 0, 0, 0, 0, 0]]
    
    def run(self):
        ctx = self.personagem.data
        
        # Cria o objeto do Spellbook resolvendo as fórmulas
        spellbook_data = {
            "config": {
                "can_multiclass": self.can_multiclass,
                "multiclass_formula": self.multiclass_formula, # String para eval futuro se necessário
                "ability_modifier": interpolate_and_eval(self.spellcasting_modifier, ctx),
                "save_dc": interpolate_and_eval(self.spell_save_dc, ctx),
                "attack_modifier": interpolate_and_eval(self.spell_attack_modifier, ctx),
                "slots_matrix": self.spellSlots,
                "recovery": self.spellSlotsRecoverOn,
                "spells_prepared_formula": self.spells_prepared,
                "spells_known_limit": self.spells_known
            },
            "spells": [] # Lista onde as magias serão armazenadas
        }

        # Define slots atuais baseados no nível do personagem (simplificação, idealmente calcula pelo nível da classe)
        # Aqui apenas salvamos a estrutura. O cálculo de slots disponíveis seria derivado.
        
        set_nested(self.personagem.data, f"spellbooks.{self.name}", spellbook_data)
        return 1

class AddSpellOperation(Operation):
    name: str
    type: str # always_prepared, known, etc.
    spellbook: str
   
    def run(self):
        # 1. Verifica se o Spellbook existe
        spellbook_path = f"spellbooks.{self.spellbook}"
        if not get_nested(self.personagem.data, spellbook_path):
            print(f"(X) Spellbook '{self.spellbook}' não encontrado.")
            return 1

        # 2. Busca a magia no BD
        # Assume que a magia está na raiz de spells.json ou acessível pelo nome
        query = f"spells/{self.name}"
        result = self.personagem.db.query(query)
        
        if not result:
            print(f"(X) Magia '{self.name}' não encontrada.")
            return 1
            
        spell_content = result.get(self.name, result)

        # 3. Adiciona a magia à lista do grimório
        spell_entry = {
            "name": self.name,
            "type": self.type,
            "data": spell_content
        }
        
        # Recupera lista atual e adiciona
        current_spells = get_nested(self.personagem.data, f"{spellbook_path}.spells")
        if current_spells is None: current_spells = []
        
        current_spells.append(spell_entry)
        set_nested(self.personagem.data, f"{spellbook_path}.spells", current_spells)
        
        return 1

class AddActionOperation(Operation):
    name: str
    cost: list[dict[str, Any]] = [] # ex: [{"resource": "x", "amount": 1}, {"action": "action"}]
    description: str = ""
    metadata: dict = {}

    def run(self):
        action_data = {
            "name": self.name,
            "cost": self.cost,
            "description": self.description,
            "metadata": self.metadata
        }
        
        # Adiciona à lista de ações disponíveis do personagem
        path = "actions"
        current_actions = get_nested(self.personagem.data, path)
        if not isinstance(current_actions, list):
            current_actions = []
            
        current_actions.append(action_data)
        set_nested(self.personagem.data, path, current_actions)
        return 1

class AddFeatureOperation(Operation):
    name: str
    description: str = ""
    operations: list[dict[str, Any]] = []

    def run(self):
        feature_data = {
            "name": self.name,
            "description": self.description
        }
        
        # 1. Salva a feature na lista de features do personagem
        path = "features"
        current_features = get_nested(self.personagem.data, path)
        if not isinstance(current_features, list):
            current_features = []
        current_features.append(feature_data)
        set_nested(self.personagem.data, path, current_features)

        # 2. Executa operações aninhadas (ex: Feature que dá Action ou Bonus)
        if self.operations:
            for op in reversed(self.operations):
                self.personagem.ficha.insert(0, op)

        return 1

class AbilityScoreImprovementOperation(Operation):
    def run(self):
        # Injeta a lógica de decisão no topo da fila de processamento
        self.personagem.ficha.insert(0, { 
            "action": "CHOOSE_OPERATIONS", 
            "n": 1, 
            "label": "Aumento no Valor de Habilidade ou Talento",
            "description": "Escolha aumentar seus atributos ou adquirir um novo talento.",
            "options": [
                {
                    "label": "+2 em um Atributo", 
                    "operations": [
                        {
                            "action": "CHOOSE_MAP", "n": 1, "label": "Escolha 1 atributo para receber +2", 
                            "options": ["str", "dex", "con", "int", "wis", "cha"], 
                            "operations": [{ "action": "INCREMENT", "property": "attributes.{THIS}.score", "value": 2 }]
                        }
                    ]
                },
                {
                    "label": "+1 em dois Atributos", 
                    "operations": [
                        {
                            "action": "CHOOSE_MAP", "n": 2, "label": "Escolha 2 atributos para receber +1", 
                            "options": ["str", "dex", "con", "int", "wis", "cha"], 
                            "operations": [{ "action": "INCREMENT", "property": "attributes.{THIS}.score", "value": 1 }]
                        }
                    ]
                },
                {
                    "label": "Talento", 
                    "operations": [
                        {
                            "action": "CHOOSE_MAP", "n": 1, "label": "Escolha um Talento", 
                            "options": { "action": "REQUEST", "query": "feats/keys" },
                            # MUDANÇA IMPORTANTE: IMPORT carrega as regras do talento (ex: Agarrador)
                            "operations": [{ "action": "IMPORT", "query": "feats/{THIS}" }]
                        }
                    ]
                }
            ]
        })
        return 1

operations = {
    "INPUT": InputOperation,
    "SET": SetOperation,
    "INCREMENT": IncrementOperation,
    "CHOOSE_MAP": ChooseMapOperation,
    "CHOOSE_OPERATIONS": ChooseOperationsOperation,
    "IMPORT": ImportOperation,
    "FOR_EACH": ForEachOperation,
    "INIT_PROFICIENCY": InitProficiencyOperation,
    "ADD_ITEM": AddItemOperation,
    "ADD_SPELLCASTING": AddSpellcastingOperation,
    "ADD_SPELL": AddSpellOperation,
    "ADD_ACTION": AddActionOperation,
    "ADD_FEATURE": AddFeatureOperation,
    "Ability_Score_Improvement": AbilityScoreImprovementOperation
}

# Personagem ========================================================================
class Character:
    def __init__(self, id: int, access_token: str, decisions: List[Any] = None):
        self.id = id
        self.access_token = access_token
        self.db = db_handler(self.access_token)
        
        self.data = {
            "decisions": decisions if decisions else [],
            "proficiency": {},
            "attributes": {}, 
            "properties": {},
            "personal": {},
            "spellbooks": {},
            "inventory": {}
        }
        self.n = 0
        self.ficha = [{"action": "IMPORT", "query": "metadata/character"}]
        self.required_decision = None

        print(f"--- Iniciando processamento Character ID {id} ---")
        self.process_queue()

    def add_race(self):
        self.n += 1 # Consome o Raça
        race = self.data["decisions"][self.n]
        self.n += 1 # Consome o nome da raça

        print(f"-> Adicionando Raça: {race}")
        self.ficha.append({"action": "IMPORT", "query": f"races/{race}"})
        self.required_decision = None 
        self.process_queue()

    def add_background(self):
        self.n += 1 # Consome o Background
        background = self.data["decisions"][self.n]
        self.n += 1 # Consome o nome do background

        print(f"-> Adicionando Background: {background}")
        self.ficha.append({"action": "IMPORT", "query": f"backgrounds/{background}"})
        self.required_decision = None 
        self.process_queue()

    def add_class(self):
        self.n += 1 # Consome a Classe
        class_name = self.data["decisions"][self.n]
        self.n += 1 # Consome o nome da Classe
        level = self.data["decisions"][self.n]
        self.n += 1 # Consome o Nível

        print(f"-> Adicionando Classe: {class_name} (Nível {level})")
        self.ficha.append({"action": "IMPORT", "query": f"classes/{class_name}/level_{level}"})

        if level != 0:
            hit_dice = self.db.query(f"classes/{class_name}/hit_dice")
            if self.get_stat("properties.level") == 1: # MÁXIMO
                self.ficha.append({"action": "SET", "property": "properties.hit_dice", "value": hit_dice})
            else:
                self.ficha.append({
                    "action": "CHOOSE_MAP", "n": 1, "label": f"Pontos de Vida (D{hit_dice})",
                    "options": [i for i in range(1, hit_dice + 1)],
                    "operations": [{ "action": "INCREMENT", "property": "properties.hit_points", "formula": "{THIS}" }]
                })

        self.required_decision = None 
        self.process_queue()

    def process_queue(self):
        self.required_decision = {}
        while len(self.ficha) > 0:
            if self.required_decision != {}:
                # print(f"(!) Processamento pausado. Aguardando: {self.required_decision['label']}")
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
        
        print(f"[N={self.n}] Exec: {action} - {op_args.get('property') or op_args.get('label') or op_args.get('query') or op_args.get('name') or ''}")

        op_class = operations.get(action)
        if not op_class: 
            return 1
        
        op_instance = op_class(personagem=self, **op_args)
        result = op_instance.run()
        
        if isinstance(result, dict):
            # print(f"    -> Pausando em {action} (Falta decisão {self.n})")
            self.ficha.insert(0, op_data)
            
        return result

    def get_basic_infos(self):
        classes = self.data["properties"]["level"].items() # [(Classe, Nível)] Para Multiclasses

        return {
            "name": self.get_stat("personal.name"),
            "race": self.get_stat("personal.subrace"),
            "background": self.get_stat("personal.background"),
            "class": classes, 
            "level": self.get_stat("level"),
        }


    def get_stat(self, path: str) -> Any:
        return resolve_value(get_nested(self.data, path), self.data)

    def update_token(self, new_token: str):
        """
        Atualiza o token de acesso da instância e do banco de dados.
        Essencial ao carregar um personagem salvo, pois o token antigo terá expirado.
        """
        self.access_token = new_token
        if self.db:
            self.db.token = new_token
            # Atualiza tokens dos sub-bancos também
            for db in self.db.db_list:
                db.token = new_token

    def to_json(self) -> str:
        """Serializa as decisões do personagem para uma string JSON"""
        return json.dumps(self.data['decisions'], indent=4, ensure_ascii=False)
       
    def to_pickle_string(self) -> str:
        """Serializa o personagem inteiro para uma string base64"""
        # Removemos temporariamente o required_decision para economizar espaço ou evitar recursão, se necessário
        # mas com dill geralmente é tranquilo.
        binary_data = pickle.dumps(self)
        return base64.b64encode(binary_data).decode('utf-8')

    @staticmethod
    def from_pickle_string(pickle_str: str, new_token: str) -> 'Character':
        """Recria o personagem a partir da string base64 e atualiza o token"""
        binary_data = base64.b64decode(pickle_str.encode('utf-8'))
        char = pickle.loads(binary_data)
        char.update_token(new_token)
        return char

# Main =======================================================
def main():
    env_token = os.getenv("JWT_TOKEN")
    env_secret = os.getenv("JWT_SECRET")
    payload = jwt.decode(env_token, env_secret, algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
    google_access_token = payload.get("google_access_token")

    decisoes_parciais = [
        "Tony Starforge",    
        15, 12, 14, 8, 8, 14,
        "Anão"
    ]
    
    print("\n--- TESTE 1: Inicialização ---")
    personagem = Character(0, access_token=google_access_token, decisions=decisoes_parciais)
    
    print("\n--- TESTE 2: Adicionando Raça (Deve Pausar) ---")
    personagem.add_race("Humano")
    
    if personagem.required_decision:
        print(f"\n>> JSON RETORNO: {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}")
    else:
        print("\n>> ERRO: Não pausou onde deveria!")

    print("\n--- TESTE 3: Retomada (Com Subraça) ---")
    personagem.data["decisions"] += ["Humano (Variante)"]
    personagem.process_queue()
    # pprint(personagem.data)
    
    if personagem.required_decision:
        print(f"\n>> JSON RETORNO (Passo 2): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}")

    # O Humano Variante escolhe 2 atributos para aumentar +1. Vamos escolher Str e Cha.
    personagem.data["decisions"] += [["str", "cha"]]
    personagem.process_queue()
    
    # Debug: Verificar se STR aumentou (era 15)
    print(f"\nForça Final: {personagem.get_stat('attributes.str.score')}")

    if personagem.required_decision:
        print(f"\n>> JSON RETORNO (Passo 3): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}")

    personagem.data["decisions"] += ["Arcanismo", "Agarrador"]
    personagem.process_queue()

    if personagem.required_decision:
        print(f"\n>> JSON RETORNO (Passo 4): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}")

    personagem.process_queue()

    if personagem.required_decision:
        print(f"\n>> JSON RETORNO (Passo 5): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}")
    else:
        print("\n>> Não pausou, mas agora finalizado")

    print("\n=== Teste de Bônus de Perícia ===")
    # Atletismo é STR. STR score 16 (+3). Proficiencia (nível 0 -> +2). Multiplicador 0 (inicial).
    # Bônus esperado: 3 + (2 * 0) = 3
    atletismo_bonus = personagem.get_stat("proficiency.skill.Atletismo.bonus")
    print(f"Bônus de Força: {personagem.get_stat('attributes.str.bonus')}")
    print(f"Bônus Atletismo (Base): {atletismo_bonus}")
    print(f'Bônus de Proficiência: {personagem.get_stat("properties.proficiency")}')

    print("-> Tornando proficiente em Atletismo...")
    personagem.data["proficiency"]["skill"]["Atletismo"]["multiplier"] = 1
    atletismo_bonus_novo = personagem.get_stat("proficiency.skill.Atletismo.bonus")
    print(f"Bônus Atletismo (Proficiente): {atletismo_bonus_novo}") # Esperado: 3 + 2 = 5

    personagem.data["decisions"] += [["Elfico", "Dracônico"], "Livro de Orações"]
    personagem.add_background("Acólito")

    print("======== Personagem Finalizado ========")
    pprint(personagem.data)

if __name__ == "__main__":
    main()
