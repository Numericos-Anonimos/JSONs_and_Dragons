import json
import os
from typing import List, Dict, Any, Union
from dataclasses import dataclass
from pprint import pprint

# Configuração de Caminhos =============================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) 
BD_DIR = os.path.join(PROJECT_ROOT, "BD")

# Banco de Dados ========================================================================

@dataclass
class db_homebrew: # Chain of responsability
    def __init__(self, endereço: str):
        self.endereço = endereço

    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        file_path = os.path.join(BD_DIR, self.endereço, f"{parts[0]}.json")
        
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                dados = json.load(f)
        else:
            # Opcional: Avisar se não encontrar, útil para debug
            # print(f"Aviso: Arquivo não encontrado: {file_path}")
            return {}

        # Navega dentro do JSON se a query tiver sub-níveis (ex: file/key/subkey)
        for i in range(1, len(parts)):
            if isinstance(dados, dict):
                dados = dados.get(parts[i], {})
            else:
                return {}
                
        return dados if isinstance(dados, dict) else {}
             

class db_handler(db_homebrew):
    def __init__(self):
        # Carrega metadados globais
        meta_path = os.path.join(BD_DIR, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                list_endereços = json.load(f).get('modules', [])
        else:
            list_endereços = []
            print("CRÍTICO: metadata.json principal não encontrado.")

        self.db_list = []
        for endereço in list_endereços:
            self.db_list.append(db_homebrew(endereço))

    def query(self, query: str):
        response = {}
        
        # Itera sobre todos os bancos de dados (módulos)
        for db in self.db_list:
            resultado_parcial = db.query(query)
            
            # LÓGICA DE CONCATENAÇÃO (MERGE)
            # Ao invés de substituir (update), nós mesclamos inteligentemente
            for key, value in resultado_parcial.items():
                if key not in response:
                    response[key] = value
                else:
                    # Se ambos forem listas, concatenamos (Ex: operations)
                    if isinstance(response[key], list) and isinstance(value, list):
                        response[key].extend(value)
                    # Se ambos forem dicionários, atualizamos chaves internas
                    elif isinstance(response[key], dict) and isinstance(value, dict):
                        response[key].update(value)
                    # Caso contrário, o último módulo vence (sobrescreve)
                    else:
                        response[key] = value
                        
        return response

# Operações ========================================================================
            
@dataclass
class Operation:
    def __init__(self, **kwargs: dict[str, Any]):
        # Remove 'personagem' dos kwargs para atribuir explicitamente
        if "personagem" in kwargs:
            self.personagem: 'Character' = kwargs.pop("personagem")
        
        for key, value in kwargs.items():
            setattr(self, key, value)

    def run(self):
        pass

class ImportOperation(Operation):
    query: str

    def run(self):
        print(f"--- Executando IMPORT: {self.query} ---")
        dados = self.personagem.db.query(self.query)

        # 1. Processa Features (se houver lógica para guardar features no personagem)
        if "features" in dados:
            # Aqui você pode salvar no self.personagem.data se quiser
            # print(f"Features encontradas: {list(dados['features'].keys())}")
            pass

        # 2. Processa Novas Operações (CRUCIAL)
        # Se o JSON importado tem uma lista de "operations", adicionamos
        # essas operações à fila de execução do personagem.
        novas_ops = dados.get("operations", [])
        pprint(novas_ops)
        if novas_ops:
            print(f"   -> Adicionando {len(novas_ops)} novas operações à fila.")
            self.personagem.ficha.extend(novas_ops)

class InputOperation(Operation):
    property: str

    def run(self):
        # { "action": "INPUT", "property": "personal.name"},
        print(f"-> Ação INPUT solicitada para: {self.property}")
        # Aqui viria a lógica de input real
        pass 

        
# Personagem ========================================================================
class Character:
    def __init__(self, id: int):
        self.id: int = id
        self.db: db_handler = db_handler()

        path_char = os.path.join(BD_DIR, "characters", str(self.id), "character.json")

        # Verifica se o personagem já existe
        if os.path.exists(path_char):
            with open(path_char, "r", encoding="utf-8") as f:
                self.data: Dict[str, Any] = json.load(f)
        else:
            self.data: Dict[str, Any] = {
                "decisions": [],
                "state": {
                    "hp": 0
                }
            }

        self.variables: Dict[str, Any] = {}
        self.dependencies: list[str] = []
        self.n: int = 0

        # Ficha começa com a instrução inicial
        self.ficha: list[Dict[str, Any]] = [
            {"action": "IMPORT", "query": "metadata/character"}
        ]

        # Loop de processamento
        # Nota: Usamos while len(ficha) porque self.ficha cresce dinamicamente
        print("Iniciando processamento do personagem...")
        while self.n < len(self.ficha):
            self.run_operation()
    
    def run_operation(self):
        op_data: Dict[str, Any] = self.ficha[self.n]
        
        # Cria uma cópia para não alterar o dict original na lista ao passar pro construtor
        op_args = op_data.copy()
        action = op_args.pop("action", None)

        op_instance = None
        match action:
            case "IMPORT":
                op_instance = ImportOperation(personagem=self, **op_args)
            case "INPUT":
                op_instance = InputOperation(personagem=self, **op_args)
            case _:
                print(f"Aviso: Ação desconhecida '{action}'\n{op_data}\n\n")

        if op_instance:
            op_instance.run()

        self.n += 1
        
def main():
    personagem = Character(0)
    print("\nProcessamento finalizado.")
    print(f"Total de operações processadas: {personagem.n}")
    # print(personagem.data) # Descomente para ver o estado final

if __name__ == "__main__":
    main()