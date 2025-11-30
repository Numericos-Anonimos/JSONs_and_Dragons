import json
import os
import re
import math
from typing import List, Dict, Any, Union, Callable
from dataclasses import dataclass
from pprint import pprint

# Configuração de Caminhos =============================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) 
BD_DIR = os.path.join(PROJECT_ROOT, "BD")

# Utils ================================================================================

def get_nested(data: Dict, path: str, default: Any = None) -> Any:
    """Busca valor em dicionário aninhado usando notação de ponto: 'key.subkey'"""
    keys = path.split('.')
    curr = data
    try:
        for key in keys:
            if isinstance(curr, dict):
                curr = curr.get(key)
            elif isinstance(curr, list) and key.isdigit():
                 curr = curr[int(key)]
            else:
                return default
            
            if curr is None:
                return default
        return curr
    except Exception:
        return default

def set_nested(data: Dict, path: str, value: Any) -> None:
    """Define valor em dicionário aninhado, criando caminhos se necessário"""
    keys = path.split('.')
    curr = data
    for i, key in enumerate(keys[:-1]):
        if key not in curr:
            curr[key] = {}
        curr = curr[key]
    curr[keys[-1]] = value

def resolve_value(value: Any, context: Dict) -> Any:
    """
    Se o valor for uma função, executa ela passando o contexto.
    Caso contrário, retorna o valor bruto.
    Isso permite 'lazy evaluation' de propriedades.
    """
    if callable(value):
        try:
            return value(context)
        except RecursionError:
            return 0
    return value

def interpolate_and_eval(text: str, context: Dict) -> Any:
    """
    1. Substitui {caminho.variavel} pelo valor no context.
    2. Se o valor for uma função, resolve ela.
    3. Se o resultado for puramente numérico/matemático, avalia.
    """
    if not isinstance(text, str):
        return resolve_value(text, context)

    # Regex para encontrar padrões {algo}
    pattern = re.compile(r'\{([a-zA-Z0-9_.]+)\}')
    
    def replacer(match):
        path = match.group(1)
        # Pega o valor bruto (pode ser func ou valor)
        raw_val = get_nested(context, path)
        # Resolve (se for func, executa)
        val = resolve_value(raw_val, context)
        
        if val is None:
            return "0" 
        return str(val)

    # Substituição
    interpolated = pattern.sub(replacer, text)

    # Tenta avaliar matematicamente se parecer uma fórmula
    if any(c in interpolated for c in "+-*/") or "floor" in interpolated:
        try:
            safe_dict = {
                "floor": math.floor,
                "ceil": math.ceil,
                "max": max,
                "min": min,
                "abs": abs
            }
            return eval(interpolated, {"__builtins__": None}, safe_dict)
        except Exception:
            pass
    
    # Tenta converter para int ou float
    try:
        if "." in interpolated:
            return float(interpolated)
        return int(interpolated)
    except ValueError:
        return interpolated

# Banco de Dados ========================================================================

@dataclass
class db_homebrew: 
    def __init__(self, endereço: str):
        self.endereço = endereço

    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        file_path = os.path.join(BD_DIR, self.endereço, f"{parts[0]}.json")
        
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                dados = json.load(f)
        else:
            return {}

        for i in range(1, len(parts)):
            if isinstance(dados, dict):
                dados = dados.get(parts[i], {})
            else:
                return {}
                
        return dados if isinstance(dados, dict) else {}
             

class db_handler(db_homebrew):
    def __init__(self):
        meta_path = os.path.join(BD_DIR, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                list_endereços = json.load(f).get('modules', [])
        else:
            list_endereços = []

        self.db_list = []
        for endereço in list_endereços:
            self.db_list.append(db_homebrew(endereço))

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

# Operações ========================================================================
            
@dataclass
class Operation:
    def __init__(self, **kwargs: dict[str, Any]):
        if "personagem" in kwargs:
            self.personagem: 'Character' = kwargs.pop("personagem")
        for key, value in kwargs.items():
            setattr(self, key, value)

    def run(self):
        pass

class ImportOperation(Operation):
    query: str
    def run(self):
        dados = self.personagem.db.query(self.query)
        novas_ops = dados.get("operations", [])
        if novas_ops:
            self.personagem.ficha.extend(novas_ops)

class InputOperation(Operation):
    property: str
    
    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        
        if not decisions:
            print(f"ERRO: Input solicitado para '{self.property}', mas não há decisões disponíveis.")
            return

        valor = decisions.pop(0)
        print(f"-> INPUT '{self.property}': {valor}")
        
        # O input sempre sobrescreve qualquer fórmula anterior com um valor estático
        set_nested(self.personagem.data, self.property, valor)

class SetOperation(Operation):
    property: str
    value: Any = None
    formula: str = None

    def run(self):
        if self.formula is not None:
            # LÓGICA REATIVA:
            # Se temos uma fórmula, armazenamos uma função (closure) que calcula 
            # o valor dinamicamente sempre que for chamada.
            formula_str = self.formula
            
            def computed_property(context):
                # O context será passado quando alguém tentar ler esse valor
                return interpolate_and_eval(formula_str, context)
            
            print(f"   SET '{self.property}' = [Fórmula Dinâmica: {self.formula}]")
            set_nested(self.personagem.data, self.property, computed_property)
        else:
            # Valor estático
            print(f"   SET '{self.property}' = {self.value}")
            set_nested(self.personagem.data, self.property, self.value)

class ForEachOperation(Operation):
    list: List[str]
    operations: List[Dict]

    def run(self):
        items = self.list
        # Se a lista for uma string com chaves {}, tenta interpolar
        if isinstance(items, str):
            # Resolve a lista do contexto (pode ser uma função que retorna lista)
            items = interpolate_and_eval(items, self.personagem.data)
            if not isinstance(items, list):
                items = [] # Fallback

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
    roll: str = "N"

    def run(self):
        # Resolve o nome usando resolve_value caso venha de fórmula
        nome_resolvido = interpolate_and_eval(self.name, self.personagem.data)
        
        prof_entry = {
            "name": nome_resolvido,
            "category": self.category,
            "multiplier": self.multiplier
        }
        if self.attributes:
            prof_entry["attribute"] = self.attributes

        current_profs = self.personagem.data.get("proficiencies", [])
        current_profs.append(prof_entry)
        self.personagem.data["proficiencies"] = current_profs
        print(f"   PROFICIENCY: {nome_resolvido} ({self.category})")


# Personagem ========================================================================
class Character:
    def __init__(self, id: int, decisions: List[Any] = None):
        self.id: int = id
        self.db: db_handler = db_handler()

        path_char = os.path.join(BD_DIR, "characters", str(self.id), "character.json")

        if os.path.exists(path_char):
            with open(path_char, "r", encoding="utf-8") as f:
                self.data: Dict[str, Any] = json.load(f)
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

        print("--- Iniciando processamento ---")
        while self.n < len(self.ficha):
            self.run_operation()
    
    def run_operation(self):
        op_data: Dict[str, Any] = self.ficha[self.n]
        op_args = op_data.copy()
        action = op_args.pop("action", None)

        op_instance = None
        match action:
            case "IMPORT":
                op_instance = ImportOperation(personagem=self, **op_args)
            case "INPUT":
                op_instance = InputOperation(personagem=self, **op_args)
            case "SET":
                op_instance = SetOperation(personagem=self, **op_args)
            case "FOR_EACH":
                op_instance = ForEachOperation(personagem=self, **op_args)
            case "INIT_PROFICIENCY":
                op_instance = InitProficiencyOperation(personagem=self, **op_args)
            case _:
                print(f"Aviso: Ação desconhecida '{action}'")

        if op_instance:
            op_instance.run()

        self.n += 1

    def get_stat(self, path: str) -> Any:
        """
        Método público para pegar uma estatística.
        Ele garante que se for uma fórmula, ela será calculada agora.
        """
        raw = get_nested(self.data, path)
        return resolve_value(raw, self.data)

    def export_data(self) -> Dict:
        """
        Gera uma versão 'limpa' do data onde todas as funções/fórmulas
        são resolvidas para seus valores atuais. Ideal para salvar JSON.
        """
        def resolve_recursive(d):
            if isinstance(d, dict):
                return {k: resolve_recursive(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [resolve_recursive(v) for v in d]
            elif callable(d):
                return d(self.data)
            else:
                return d
        
        return resolve_recursive(self.data)
        
def main():
    decisoes_mock = [
        "Tony Starforge",    # nome
        15, 12, 14, 8, 8, 14 # atributos
    ]

    personagem = Character(0, decisions=decisoes_mock)
    
    # TESTE DE REATIVIDADE
    print("\n=== Teste de Reatividade ===")
    
    # 1. Pega valor original
    str_mod_original = personagem.get_stat("attributes.str.modifier")
    print(f"Modificador de Força (Score 15): {str_mod_original}") # Esperado: 2

    # 2. Altera o atributo base (simulando aumento de atributo)
    print("-> Aumentando Força para 18...")
    personagem.data['attributes']['str']['score'] = 18

    # 3. Verifica se o modificador e o save mudaram sozinhos
    str_mod_novo = personagem.get_stat("attributes.str.modifier")
    str_save_novo = personagem.get_stat("attributes.str.save")
    
    print(f"Modificador de Força (Score 18): {str_mod_novo}") # Esperado: 4
    print(f"Save de Força (Baseado no mod): {str_save_novo}")   # Esperado: 4

    print("\n=== Exportação JSON (Preview) ===")
    final_json = personagem.export_data()
    pprint(personagem.data)

if __name__ == "__main__":
    main()