import json
import os
from typing import List, Dict, Any
from dataclasses import dataclass
from pprint import pprint

# Banco de Dados ========================================================================

@dataclass
class db_homebrew: # Chain of responsability
    def __init__(self, endereço: str):
        self.endereço = endereço

    def query(self, query: str):
        query = query.split("/")
        file = f"BD/{self.endereço}/{query[0]}.json"
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                dados = json.load(f)
        else:
            dados = {}

        for i in range(1, len(query)):
            dados = dados.get(query[i], {})
        return dados
         

class db_handler(db_homebrew):
    def __init__(self):
        with open("BD/metadata.json", "r", encoding="utf-8") as f:
            list_endereços = json.load(f)['modules']

        self.db_list = []
        for endereço in list_endereços:
            self.db_list.append(db_homebrew(endereço))

    def query(self, query: str):
        response = {}
        for db in self.db_list:
            response.update(db.query(query))
        return response

db = db_handler()



# Operações ========================================================================
            
@dataclass
class ImportOperation:
    query: str

    def __init__(self, **kwargs: dict[str, Any]):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def run(self):
        global db
        dados = db.query(self.query)
        pprint(dados.get("operations", {}))
        pprint(dados.get("features", {}))

class InputOperation:
    def __init__(self, **kwargs: dict[str, Any]):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def run(self):
        

        
# Personagem ========================================================================
class Character:
    def __init__(self, id: int):
        self.id = id

        # Verifica se o personagem já existe (sempre ler jsons em utf-8)
        if os.path.exists(f"BD/characters/{self.id}/character.json"):
            with open(f"BD/characters/{self.id}/character.json", "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "decisions": [],
                "state": {
                    "hp": 0
                }
            }

        self.variables: Dict[str, Any] = {}
        self.dependencies: list[str] = []
        self.n: int = 0

        self.ficha: list[Dict[str, Any]] = [
            {"action": "IMPORT", "query": "metadata/character"}
        ]

        while self.n < len(self.ficha):
            self.run_operation()
    
    def run_operation(self):
        op: Dict[str, Any] = self.ficha[self.n]
        if op["action"] == "IMPORT":
            op = ImportOperation(**op)
        op.run()
        self.n += 1   

        



        
def main():
    personagem = Character(0)
    #print(personagem.data)


if __name__ == "__main__":
    main()
    