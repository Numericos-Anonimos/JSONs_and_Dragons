# tests/test_character.py
import json
from pathlib import Path

# Supondo que a classe Character estará em jsons_and_dragons/character.py
from jsons_and_dragons.character import Character 

def test_load_character_from_json():
    """
    Testa se é possível carregar os dados básicos de um personagem de um arquivo JSON.
    """
    # Caminho para o arquivo JSON de teste
    json_path = Path(__file__).parent.parent / "Kaelen.json"
    
    # Cria uma instância do personagem a partir do JSON
    kaelen = Character(json_path)
    
    # Asserts: Verificações que o teste faz
    assert kaelen.name == "Kaelen, o Vingador"
    assert kaelen.level == 4
    assert kaelen.player_name == "JSONs & Dragons"

