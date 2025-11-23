# 1. Arquivos Essenciais (O Banco de Dados)

Para cobrir D&D 5e 2014 e permitir expansão, eu sugiro dividir os JSONs por **Tipo de Entidade**. O _Chain of Responsibility_ (SRD -> Tasha -> Homebrew do Zé) vai carregar esses arquivos em memória ou indexá-los.

**Estrutura de Diretórios Sugerida:**
```Plaintext
/DATASET_NAME (ex: SRD)
  - meta.json        (Nome do livro, autor, versão)
  - classes.json     (Definição de classes e feature progression)
  - subclasses.json  (Definição de subclasses)
  - races.json       (Raças)
  - subraces.json    (Sub-raças)
  - backgrounds.json (Antecedentes)
  - items.json       (Equipamentos, Itens Mágicos, Loot)
  - spells.json      (Magias)
  - feats.json       (Talentos)
  - features.json    (Features soltas referenciadas por ID, ex: Estilos de Luta, Invocações de Bruxo, Linguas, Proficiências)
  - monsters.json    (Para o futuro: formas selvagens de druida, familiares, etc)
```

# 2. O Sistema de Tags e Query (Metadata)

Para que `CHOOSE` e `GRANT` funcionem sem hardcoding, todo objeto precisa de um objeto `metadata` robusto. Não vamos usar apenas strings soltas, mas sim pares de chave-valor para filtros precisos.

**Exemplo de Estrutura de Item (Espada Longa):**
```json
{
  "id": "longsword",
  "name": "Espada Longa",
  "type": "weapon",
  "metadata": {
    "category": "martial",
    "range_type": "melee",
    "damage_type": "slashing",
    "properties": ["versatile", "heavy"], 
    "cost_gp": 15
  },
  ...
}
```

**Como a Query Funciona (Exemplos):**
1. **Paladino Nível 1:** "Escolha uma arma marcial".   
    - _Query:_ `type == 'weapon' AND metadata.category == 'martial'`
2. **Mago aprendendo magia:** "Escolha magias da lista de mago".
    - _Query:_ `type == 'spell' AND 'wizard' in metadata.classes`

# 3. Catálogo de Operações (A "Linguagem")
Para padronizar, vamos dividir as operações em **Mutação de Estado** (alteram a ficha) e **Definição de Efeito** (alteram cálculos temporários).

## A. Operações 

|**Verbo**|**Parâmetros**|**Descrição**|
|---|---|---|
|`SET`|`key`, `value` (ou `formula`)|Define um valor base (ex: `attributes.str = 15`).|
|`INCREMENT`|`key`, `value`|Soma ao valor existente (ex: `attributes.str += 1`).|
|`APPEND`|`list_key`, `value`|Adiciona a uma lista (ex: adicionar "Orc" em `languages`).|
|`GRANT_PROFICIENCY`|`type`, `target`|_Syntax Sugar_ para `APPEND` em listas de skills/saves.|
|`CHOOSE`|`n`, `query` (ou `options`), `output_target`|Pausa o processamento e pede input do usuário. O resultado gera uma nova operação salva no `evolution`.|
|`ADD_FEATURE`|`reference`|Adiciona uma feature (ex: Talento) buscando pelo ID/Reference.|
|`GRANT_ACTION`|`action_object`|Confere uma ação ao jogador (Ataque, Magia, Habilidade).|

# 4. Exemplo Prático: O Paladino e a Espada
1. O Item (items.json): Note o array de dano para suportar múltiplos tipos.

```json
{
  "id": "longsword",
  "name": "Espada Longa",
  "type": "weapon",
  "metadata": {
    "category": "martial",
    "properties": ["versatile"]
  },
  "effects": [
    {
      "condition": "equipped", 
      "action": "GRANT_ACTION",
      "data": {
        "name": "Ataque (Espada Longa)",
        "type": "attack",
        "range": "5ft",
        "attack_bonus_formula": "properties.proficiency + properties.mod_str",
        "damage": [
          { 
            "formula": "1d8 + properties.mod_str", 
            "type": "slashing" 
          }
        ],
        "versatile_damage": [
           { 
            "formula": "1d10 + properties.mod_str", 
            "type": "slashing" 
          }
        ]
      }
    }
  ]
}
```

2. A Classe Paladino (classes.json): Note o uso da Query no CHOOSE.

```json
{
  "id": "paladin",
  "name": "Paladino",
  "hit_dice": "1d10",
  "progression": {
    "1": {
      "operations": [
        { "action": "SET", "key": "resources.hit_dice_max", "formula": "level" },
        { 
          "action": "CHOOSE", 
          "n": 1, 
          "query": { "type": "weapon", "metadata.category": "martial" },
          "description": "Escolha uma arma marcial para seu equipamento inicial."
        },
        {
          "action": "GRANT_PROFICIENCY",
          "type": "armor",
          "tags": ["light", "medium", "heavy", "shield"]
        }
      ],
      "features": [
        { 
           "name": "Sentido Divino",
           "description": "...",
           "operations": [
             { 
               "action": "SET", 
               "key": "counters.sentido_divino.max", 
               "formula": "1 + properties.mod_cha" 
             }
           ]
        }
      ]
    }
  }
}
```