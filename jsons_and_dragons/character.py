# jsons_and_dragons/character.py
import json

class Character:
    """
    Representa uma ficha de personagem de D&D, construída a partir
    de uma série de operações definidas em um arquivo JSON.
    """
    def __init__(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # O nome do personagem ainda está no mesmo lugar.
        self.name = data["characterName"]
        
        # Para calcular o nível, contamos quantos blocos do tipo "LEVEL_UP"
        self.level = 0
        if "evolution" in data:
            for event in data["evolution"]:
                if event.get("type") == "LEVEL_UP":
                    self.level += 1
