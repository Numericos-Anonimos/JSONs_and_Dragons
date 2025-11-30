import json
import os
import re
import math
from typing import List, Dict, Any, Union
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

def interpolate_and_eval(text: str, context: Dict) -> Any:
    """
    1. Substitui {caminho.variavel} pelo valor no context.
    2. Se o resultado for puramente numérico/matemático, avalia.
    """
    if not isinstance(text, str):
        return text

    # Regex para encontrar padrões {algo}
    pattern = re.compile(r'\{([a-zA-Z0-9_.]+)\}')
    
    def replacer(match):
        path = match.group(1)
        val = get_nested(context, path)
        if val is None:
            # Se não achar, retorna 0 para evitar quebra de matemática, 
            # ou mantém a string se for texto.
            return "0" 
        return str(val)

    # Substituição
    interpolated = pattern.sub(replacer, text)

    # Tenta avaliar matematicamente se parecer uma fórmula
    # Permitimos caracteres matemáticos básicos e funções seguras
    allowed_math = set("0123456789+-*/()., ")
    
    # Verifica se a string contém apenas caracteres matemáticos ou chamadas de função simples
    # Hack simples: se tem 'floor', 'ceil' ou operadores, tentamos eval
    if any(c in interpolated for c in "+-*/") or "floor" in interpolated:
        try:
            # Contexto seguro para o eval
            safe_dict = {
                "floor": math.floor,
                "ceil": math.ceil,
                "max": max,
                "min": min,
                "abs": abs
            }
            return eval(interpolated, {"__builtins__": None}, safe_dict)
        except Exception:
            # Se der erro no eval, retorna a string interpolada (pode ser texto normal)
            pass
    
    # Tenta converter para int ou float se possível
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
            
            # Merge Recursivo Simplificado
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
        # print(f"--- IMPORT: {self.query} ---")
        dados = self.personagem.db.query(self.query)
        
        novas_ops = dados.get("operations", [])
        if novas_ops:
            # Adiciona ao final da fila
            self.personagem.ficha.extend(novas_ops)

class InputOperation(Operation):
    property: str
    
    def run(self):
        # Simula frontend: consome da lista de decisões
        decisions = self.personagem.data.get("decisions", [])
        
        if not decisions:
            print(f"ERRO: Input solicitado para '{self.property}', mas não há decisões disponíveis.")
            return

        valor = decisions.pop(0)
        print(f"-> INPUT '{self.property}': {valor}")
        
        set_nested(self.personagem.data, self.property, valor)

class SetOperation(Operation):
    property: str
    value: Any = None
    formula: str = None

    def run(self):
        final_value = self.value
        
        # Se tiver fórmula, calcula
        if self.formula is not None:
            final_value = interpolate_and_eval(self.formula, self.personagem.data)
            
        print(f"   SET '{self.property}' = {final_value}")
        set_nested(self.personagem.data, self.property, final_value)

class ForEachOperation(Operation):
    list: List[str]
    operations: List[Dict]

    def run(self):
        # A lista pode ser estática ou vir de uma variável {path}
        items = self.list
        if isinstance(items, str) and "{" in items:
            # Lógica simples para pegar lista de variável se necessário
            pass 

        # Para cada item na lista, cria cópias das operações substituindo {THIS}
        expanded_ops = []
        for item in items:
            for op_template in self.operations:
                # Serializa e deserializa para garantir cópia profunda simples
                op_str = json.dumps(op_template)
                # Substituição literal de {THIS}
                op_str = op_str.replace("{THIS}", str(item))
                new_op = json.loads(op_str)
                expanded_ops.append(new_op)
        
        # Injeta as novas operações IMEDIATAMENTE após a atual
        # para manter a ordem lógica (Depth-first)
        # Inserimos em ordem reversa para que fiquem na ordem certa na pilha
        for op in reversed(expanded_ops):
            self.personagem.ficha.insert(self.personagem.n + 1, op)

class InitProficiencyOperation(Operation):
    category: str
    name: str
    attributes: str = None
    multiplier: int = 0
    roll: str = "N"

    def run(self):
        # Resolve o nome (pode ter vindo de um {THIS})
        nome_resolvido = interpolate_and_eval(self.name, self.personagem.data)
        
        prof_entry = {
            "name": nome_resolvido,
            "category": self.category,
            "multiplier": self.multiplier
        }
        if self.attributes:
            prof_entry["attribute"] = self.attributes

        # Salva em uma lista de proficiências no data
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
                "proficiencies": [], # Armazena resultado do INIT_PROFICIENCY
                "attributes": {},    # Necessário para os SETs de atributo
                "properties": {},    # Necessário para level, etc
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
        
def main():
    # Simulando as decisões vindas do Front-end para o exemplo do Paladino Humano
    decisoes_mock = [
        "Tony Starforge",    # nome
        15, 12, 14, 8, 8, 14 # atributos (str, dex, con, int, wis, cha)
        # O resto das decisões viriam aqui conforme o fluxo progride...
    ]

    personagem = Character(0, decisions=decisoes_mock)
    
    print("\n=== Estado Final (Parcial) ===")
    pprint(personagem.data.get("attributes"))
    pprint(personagem.data.get("properties"))
    print("Proficiências:", len(personagem.data.get("proficiencies", [])))

if __name__ == "__main__":
    main()