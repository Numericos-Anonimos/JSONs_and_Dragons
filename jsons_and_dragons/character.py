import json


class Character:
    """
    Representa uma ficha de personagem de D&D, construída a partir
    de uma série de operações definidas em um arquivo JSON.
    """
    def __init__(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.name = self.data["characterName"]
        
        # O dicionário 'properties' irá armazenar o estado final do personagem
        self.properties = {}
        self._process_character()

    def _process_operations(self, operations):
        """Processa uma lista de operações e atualiza as propriedades."""
        for op in operations:
            action = op["action"]
            prop = op.get("property")
            
            if action == "SET":
                self.properties[prop] = op["value"]
            elif action == "INCREMENT":
                # Garante que a propriedade exista antes de incrementar
                if prop not in self.properties:
                    self.properties[prop] = 0
                self.properties[prop] += op["value"]
    
    def _process_character(self):
        """Processa toda a evolução e inventário para construir o personagem."""
        # 1. Processa a evolução (atributos base, raça, níveis)
        for event in self.data.get("evolution", []):
            if "operations" in event:
                self._process_operations(event["operations"])
        
        # 2. Processa os itens equipados no inventário
        for item in self.data.get("inventory", []):
            if item.get("equipped") and "operations" in item:
                self._process_operations(item["operations"])

    def get_attribute(self, name: str) -> int:
        """Retorna o valor final de um atributo (ex: 'Força')."""
        # Acessa a propriedade que foi calculada, ex: 'Força_base'
        return self.properties.get(f"{name}_base", 0)

    def get_modifier(self, name: str) -> int:
        """Calcula e retorna o modificador de um atributo."""
        score = self.get_attribute(name)
        return (score - 10) // 2
        
    @property
    def level(self) -> int:
        """Calcula o nível total do personagem."""
        lvl = 0
        for event in self.data.get("evolution", []):
            if event.get("type") == "LEVEL_UP":
                lvl += 1
        return lvl
