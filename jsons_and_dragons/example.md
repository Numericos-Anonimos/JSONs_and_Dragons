# Testes de Escolhas
## Teste 1: Nível 0 de Paladino
Ponto de partida:
```json
"level_0": {
    "operations": [
        { "action": "INCREMENT", "property": "proficiency.wis.save", "formula": 1 },
        { "action": "INCREMENT", "property": "proficiency.cha.save", "formula": 1 },
        { "action": "SET", "property": "proficiency.armor.Pesada.multiplier", "value": 1 },
        { 
            "action": "CHOOSE_MAP", "n": 2, "label": "Perícias de Paladino",
            "options": ["Atletismo", "Intimidação", "Intuição", "Medicina", "Persuasão", "Religião"],
            "operations": [{"action": "SET", "property": "proficiency.skill.{THIS}.multiplier", "value": 1}]
        },
        { 
            "action": "CHOOSE_OPERATIONS", "n": 1, "label": "Equipamento Inicial A",
            "options": [
                {
                    "label": "Escudo e Arma Marcial",
                    "operations": [
                        { "action": "ADD_ITEM", "query": "items/name == 'Escudo'" },
                        { "action": "CHOOSE_MAP", "n": 1, "label": "Arma Marcial",
                            "options": {"action": "REQUEST", "query": "items/Armas/metadata.category == Marcial/name"},
                            "operations": [{"action": "ADD_ITEM", "query": "items/Armas/name == '{THIS}'"}]
                        }
                    ]
                },
                {
                    "label": "Duas Armas Marciais",
                    "operations": [
                        { "action": "CHOOSE_MAP", "n": 2, "label": "Arma Marcial",
                            "options": {"action": "REQUEST", "query": "items/Armas/metadata.category == Marcial/name"},
                            "operations": [{"action": "ADD_ITEM", "query": "items/Armas/name == '{THIS}'"}]
                        }
                    ]
                }
            ]
        },
        { 
            "action": "CHOOSE_OPERATIONS", "n": 1, "label": "Equipamento Inicial B",
            "options": [
                {
                    "label": "Cinco Azagaias",
                    "operations": [{ "action": "ADD_ITEM", "amount": 5, "query": "items/name == 'Azagaia'" }]
                },
                {
                    "label": "Arma Simples Corpo-a-Corpo",
                    "operations": [
                        { "action": "CHOOSE_MAP", "n": 1, "label": "Arma Simples Corpo-a-Corpo",
                            "options": {"action": "REQUEST", "query": "items/metadata.type == 'weapon' AND metadata.category == 'simple' AND metadata.melee == true/name"},
                            "operations": [{"action": "ADD_ITEM", "name": "{THIS}", "query": "items/name == '{THIS}'"}]
                        }
                    ]
                }
            ]
        },
        { 
            "action": "CHOOSE_OPERATIONS", "n": 1, "label": "Equipamento Inicial C",
            "options": [
                { "label": "Pacote de Sacerdote", "operations": [{ "action": "ADD_ITEM", "query": "items/name == 'Pacote de sacerdote'" }] },
                { "label": "Pacote de Aventureiro", "operations": [{ "action": "ADD_ITEM", "query": "items/name == 'Pacote de aventureiro'" }] }
            ]
        },
        { "action": "ADD_ITEM", "query": "items/name == 'Cota de malha'" },
        { "action": "ADD_ITEM", "name": "Símbolo sagrado (Foco Arcano)", "query": "items/name == 'Símbolo sagrado'" }
    ]
},
```

Retorno para o frontend:
```json
[
    {
        "label": "Perícias de Paladino", "n": 2,
        "options": ["Atletismo", "Intimidação", "Intuição", "Medicina", "Persuasão", "Religião"],
    },
    {
        "label": "Equipamento Inicial A", "n": 1,
        "options": ["Escudo e Arma Marcial", "Duas Armas Marciais"],
        "related": [1, 1] // Opção 1 possuí 1 subescolha, opção 2 possuí 1 subescolha
    },
    {
        "label": "Arma Marcial", "n": 1,
        "options": [...], // Lista de armas marciais
    },
    {
        "label": "Arma Marcial", "n": 2,
        "options": [...], // Lista de armas marciais
    },
    {
        "label": "Equipamento Inicial B", "n": 1,
        "options": ["Cinco Azagaias", "Arma Simples Corpo-a-Corpo"],
        "related": [0, 1] // Opção 1 possuí 0 subescolhas, opção 2 possuí 1 subescolha
    },
    {
        "label": "Arma Simples Corpo-a-Corpo", "n": 1,
        "options": [...], // Lista de armas simples corpo-a-corpo
    },
    {
        "label": "Equipamento Inicial C", "n": 1,
        "options": ["Pacote de Sacerdote", "Pacote de Aventureiro"],
        "related": [0, 0] // Opção 1 possuí 0 subescolhas, opção 2 possuí 0 subescolhas
    }
]
```

Respostas possíveis do frontend:
- ["Atletismo", "Escudo e Arma Marcial", "Machado de Guerra", "Cinco Azagaias", "Pacote de Sacerdote"]
- ["Medicina", "Duas Armas Marciais", ["Arco Longo", "Espada Longa"], "Arma Simples Corpo-a-Corpo", "Adaga", "Pacote de Aventureiro"]

Saída final:
```json
???
```

## Teste 2: Humano Variante:
Entradas Brutas:
- Humano:
```json
"Humano": {
    "features": [
        { "action": "SET", "property": "personal.race", "value": "Humano" },
        {
            "action": "CHOOSE_MAP", "n": 1, "label": "Subraça",
            "options": {"action": "REQUEST", "query": "subraces/metadata.race == 'Humano'/name"},
            "operations": [{"action": "IMPORT", "query": "subraces/name == '{THIS}'"}]
        },
        {"action": "SET", "property": "attributes.speed", "value": "9"},
        {"action": "SET", "property": "attributes.size", "value": "Médio"},  
        {"action": "IMPORT", "query": "features/name == 'Comum'"},
        {
            "action": "CHOOSE_MAP", "n": 1, "label": "Idioma Adicional", 
            "options": {"action": "REQUEST", "query": "features/metadata.type == 'language'/name"},
            "operations": [{"action": "IMPORT", "query": "features/name == '{THIS}'"}]
        }
    ]
},
```
- Subraças:
```json
"Humano (Comum)": {
    "metadata": { "race": "Humano" },
    "operations": [
        {"action": "SET", "property": "personal.subrace", "value": "Humano (Comum)"},
        {"action": "INCREMENT", "property": "attributes.str.score", "formula": 1},
        {"action": "INCREMENT", "property": "attributes.dex.score", "formula": 1},
        {"action": "INCREMENT", "property": "attributes.con.score", "formula": 1},
        {"action": "INCREMENT", "property": "attributes.int.score", "formula": 1},
        {"action": "INCREMENT", "property": "attributes.wis.score", "formula": 1},
        {"action": "INCREMENT", "property": "attributes.cha.score", "formula": 1}
    ]
},
"Humano (Variante)": {
    "metadata": { "race": "Humano" },
    "operations": [
        {"action": "SET", "property": "personal.subrace", "value": "Humano (Variante)"},
        {
            "action": "CHOOSE_MAP", "n": 2, "label": "Aumento no Valor de Habilidade",
            "options": ["str", "dex", "con", "int", "wis", "cha"],
            "operations": [{"action": "INCREMENT", "property": "attributes.{THIS}.score", "formula": 1}]
        },
        { 
            "action": "CHOOSE_MAP", "n": 1, "label": "Perícia",
            "options": ["Acrobacia", "Adestrar Animais", "Arcanismo", "Atletismo", "Atuação", "Enganação", "Furtividade", "História", "Intimidação", "Intuição", "Investigação", "Medicina", "Natureza", "Percepção", "Persuasão", "Prestidigitação", "Religião", "Sobrevivência"],
            "operations": [{"action": "SET", "property": "proficiency.skill.{THIS}.multiplier", "value": 1}]
        },
        { 
            "action": "CHOOSE_MAP", "n": 1, "label": "Talento",
            "options": {"action": "REQUEST", "query": "feats/name"},
            "operations": [{"action": "IMPORT", "query": "feats/name == '{THIS}'"}]
        }
    ]
},
```

Retorno para o frontend:
```json
[
    {
        "label": "Subraça", "n": 1,
        "options": ["Humano (Comum)", "Humano (Variante)"],
        "related": [0, 3]
    },
    {
        "label": "Aumento no Valor de Habilidade", "n": 2,
        "options": ["str", "dex", "con", "int", "wis", "cha"]
    },
    {
        "label": "Perícia", "n": 1,
        "options": ["Acrobacia", "Adestrar Animais", "Arcanismo", "Atletismo", "Atuação", "Enganação", "Furtividade", "História", "Intimidação", "Intuição", "Investigação", "Medicina", "Natureza", "Percepção", "Persuasão", "Prestidigitação", "Religião", "Sobrevivência"]
    },
    {
        "label": "Talento", "n": 1,
        "options": ["Agarrador"]
    },
    {
        "label": "Idioma Adicional", "n": 1,
        "options": ["Comum", "Élfico", "Anão", "Dracônico"]
    }
]
```

Respostas possíveis do frontend:
- ["Humano (Variante)", ["str", "dex"], "Acrobacia", "Agarrador", "Élfico"]
- ["Humano (Comum)", "Anão"]

Saída final:
```json
???
```