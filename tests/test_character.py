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
    json_path = Path(__file__).parent / "Kaelen.json" 
    
    # Cria uma instância do personagem a partir do JSON
    kaelen = Character(json_path)
    
    # Asserts: Verificações que o teste faz
    assert kaelen.name == "Kaelen, o Vingador"
    assert kaelen.level == 4

def test_calculate_final_attributes_and_modifiers():
    """
    Testa se os atributos e modificadores finais são calculados corretamente,
    processando a evolução e os itens equipados.
    """
    json_path = Path(__file__).parent / "Kaelen.json"
    kaelen = Character(json_path)

    # Verificando os valores finais dos atributos
    # Força: 15 (base) + 1 (racial) = 16
    assert kaelen.get_attribute("Força") == 16
    assert kaelen.get_modifier("Força") == 3  # Modificador de +3 para Força 16

    # Destreza: 10 (base) = 10
    assert kaelen.get_attribute("Destreza") == 10
    assert kaelen.get_modifier("Destreza") == 0  # Modificador de +

    # Constituição: 13 (base) = 13
    assert kaelen.get_attribute("Constituição") == 13
    assert kaelen.get_modifier("Constituição") == 1  # Modificador de +1 para Constituição 13

    # Inteligência: 8 (base) = 8
    assert kaelen.get_attribute("Inteligência") == 8
    assert kaelen.get_modifier("Inteligência") == -1  # Modificador de -1 para Inteligência 8

    # Sabedoria: 12 (base) + 2 (item) = 14
    assert kaelen.get_attribute("Sabedoria") == 14
    assert kaelen.get_modifier("Sabedoria") == 2  # Modificador de +2 para Sabedoria 14

    # Carisma: 14 (base) + 1 (racial) = 15
    assert kaelen.get_attribute("Carisma") == 15
    assert kaelen.get_modifier("Carisma") == 2  # Modificador de +2 para Carisma 15
