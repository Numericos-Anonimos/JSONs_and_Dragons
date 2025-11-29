# Documentação Técnica: Engine de Fichas D&D 5e (JSON-Driven)

## 1. Visão Geral da Arquitetura
O sistema funciona baseada em **Entidades** (Classes, Raças, Itens) que aplicam **Operações** (Mutações de estado) na **Ficha do Personagem** (Contexto). A arquitetura permite expansão infinita através de "Camadas de Conteúdo" (Sources).

**Estrutura de Diretórios:**
```Plaintext
/DATASET_NAME (ex: SRD)
  - meta.json        (Nome do livro, autor, versão, características básicas da ficha)
  - classes.json     (Definição de classes e feature progression)
  - subclasses.json  (Definição de subclasses)
  - races.json       (Raças)
  - subraces.json    (Sub-raças)
  - backgrounds.json (Antecedentes)
  - items.json       (Equipamentos, Itens Mágicos, Loot)
  - spells.json      (Magias)
  - feats.json       (Talentos)
  - features.json    (Features soltas referenciadas por ID, ex: Estilos de Luta, Invocações de Bruxo, Linguas, Proficiências)
```
## 2. Estrutura de Dados (Schemas)
Todo arquivo JSON deve seguir o padrão de dicionário onde a **Chave** é o ID único (Nome) e o **Valor** é o objeto da entidade.
### 2.1. Objeto Entidade Padrão
Todas as entidades (Item, Spell, Feature, Class) herdam desta estrutura:
```
"Nome da Entidade": {
  "metadata": {
    "type": "string",       // ex: "weapon", "spell", "class"
    "source": "string",     // ex: "PHB", "Tasha"
    "requirements": {}      // Opcional: Dicionário de pré-requisitos
  },
  "description": "Markdown string",
  "operations": []          // Lista de comandos a executar
}
```
### 2.2. Sistema de Metadados e Filtros
- O campo `metadata` é indexado para buscas rápidas (`REQUEST`).
- **Requirements:** Expressões que, se falsas, impedem o uso/equipamento.
    - Ex: `"strength": "attributes.str.score >= 13"`

## 3. Linguagem de Operações (DSL)
As operações definem como uma entidade altera a ficha.

### Ações de Estado (State Mutators)

| Ação        | Descrição                                                          | Exemplo                                                                                                                                                           |
| ----------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SET`       | Define um valor absoluto.                                          | `{ "action": "SET", "property": "personal.race", "value": "Humano" }`                                                                                             |
| `INCREMENT` | Soma ao valor atual.                                               | `{ "action": "SET", "property": "resources.sentido_divino", "type": "counter", "formula": "max(1, 1 + {attributes.carisma.modifier})", "recoversOn": "long_rest" }` |
| `INIT`      | Cria a variável se não existir. Útil para recursos compartilhados. | `{ "action": "INIT", "property": "resources.canalizar_divindade", "type": "counter", "value": 1, "recoversOn": "short_rest" }`                                    |

- **Parâmetros Obrigatórios:**
	- `property`: Chave onde o valor será / está armazenado.
	- `value`/`formula`: O valor assume um valor fixo, enquanto a formula é avaliada quando necessário.
- **Parâmetros Opcionais:**
	- `type`: Define o tipo da propriedade, pode ser `value` (padrão), `counter` (cria um máximo e a quantidade utilizada) ou `list` (cria uma lista de valores).
	- `recoversOn`: No caso de um counter, define quando ele recupera. Pode ser `short_rest`, `long_rest` ou `never` (padrão).

Utilizar o ponto cria um novo dicionário. Por exemplo: attributes.str.score -> variaveis\[attributes\]\[str\]\[score\]. Isso permite pegar a lista de proeficiencia em perícias rapidamente.

### Ações de Inventário e Conhecimento
#### Adicionar Itens:
- **Parâmetros:**
	- `query`: Caminho para encontrar um item.
	- `amount` (Opcional): Quantidade que deve ser adicionada
	- `name` (Opcional): Caso definido, adiciona um nickname ao item.
- **Exemplo:**
```json
{"action": "ADD_ITEM", "amount": 5, "query": "items/name == 'Azagaia'"}
```

#### Adicionar Conjuração e Magias:
Para adicionarmos as magias, precisamos criar um speelbook antes. Ele define como essa conjuração funciona e como ela interage com multiclasse mágica.

```json
{
    "action": "ADD_SPELLCASTING", 
    "name": "Paladino",
    "can_multiclass": true,
    "multiclass_formula": "floor({properties.level.Paladino} / 2)",
    "spellcastig_modifier": "{attributes.cha.modifier}",
    "spell_save_dc": "8 + {properties.proficiency_bonus} + {attributes.cha.modifier}",
    "spell_attack_modifier": "{properties.proficiency_bonus} + {attributes.cha.modifier}",
    "spells_prepared": "max(1, {attributes.cha.modifier} + floor({properties.level.Paladino} / 2))",
    "spells_known": "infinity",
    "spellSlotsRecoverOn": "long_rest",
    "spellbook_query": "spells/'Paladino' in metadata.classes",
    "spellSlots": [
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [2, 0, 0, 0, 0, 0, 0, 0, 0],
        [3, 0, 0, 0, 0, 0, 0, 0, 0],
        [3, 0, 0, 0, 0, 0, 0, 0, 0],
        [4, 2, 0, 0, 0, 0, 0, 0, 0],
        [4, 2, 0, 0, 0, 0, 0, 0, 0],
        [4, 3, 0, 0, 0, 0, 0, 0, 0],
        [4, 3, 0, 0, 0, 0, 0, 0, 0],
        [4, 3, 2, 0, 0, 0, 0, 0, 0],
        [4, 3, 2, 0, 0, 0, 0, 0, 0]
    ]
}
```

Com o spellbook criado, podemos utilizar ele como alvo para adicionar uma magia:
```json
{ "action": "ADD_SPELL", "name": "Sinal de esperança", "type": "always_prepared", "spellbook": "Paladino" },
```

As opções para type são: `always_prepared`, `always_known`, `prepared`, `known`

### Adicionar Ação
As ações normalmente estão encapsuladas por features ou itens, dessa forma não precisam de descrição:

```json
{ "action": "ADD_ACTION", "name": "Cura pelas Mãos", "cost": [{"resource": "cura_pelas_maos", "amount": "x"}, {"action": "action"}] }
```

O custo pode ser um recurso (propriedade contador), uma ação (ação) ou um spellslot (spellslot).

### Adicionar Proficiência
Primeiramente a proficiência deve ser criada no personagem. Todos os atributos são obrigatórios.
```json
{ "action": "INIT_PROFICIENCY", "category": "skill", "name": "{THIS}", "multiplier": 0, "attributes": "int", "roll": "N" }
```

Na prática, esses valores também vão ser armazenados como propriedades. Quando o usuário acessar variáveis\[proficiency\]\[skill\]\[atletismo\] ele vai receber:
```json
{
	"name": "atletismo",
	"multiplier": 0,
	"atributes": "int",
	"roll": "N",
	"formula": "{atributes.int.bonus} + 0 * {properties.proficiency}"
}
```

O bônus final é calculado pela fórmula: `atributes.{atributes}.bonus + multiplier * proeficiencia`. Isso permite flexibilidade para mecânicas como "Expertise" (Maestria) ou "Jack of all Trades" do Bardo: basta aplicar um `SET` na propriedade `proficiency.skill.atletismo.multiplier`. Para itens que impõem desvantagem (como armaduras pesadas em Furtividade), basta alterar o `roll` para `"D"`.

### Ações de Fluxo de Controle
#### Fazendo Escolhas:
- `CHOOSE_MAP`: Apresenta uma escolha ao usuário. O resultado substitui a variável `THIS` na `operations` subsequente.
```json
{
	"action": "CHOOSE_MAP", "n": 2, "label": "Perícias de Paladino",
	"options": ["Atletismo", "Intimidação", "Intuição", "Medicina", "Persuasão", "Religião"],
	"operations": [{"action": "SET", "property": "proficiency.skill.{THIS}.multiplier", "value": 1}]
}
```

- `CHOOSE_OPERATIONS`: Apresenta opções onde cada opção é um pacote fechado de operações (ex: Kits iniciais).
```json
{ 
	"action": "CHOOSE_OPERATIONS", "n": 1, "label": "Equipamento Inicial C",
	"options": [
		{ "label": "Pacote de Sacerdote", "operations": [{ "action": "ADD_ITEM", "name": "Pacote de Sacerdote", "query": "items/name == 'Pacote de sacerdote'" }] },
		{ "label": "Pacote de Aventureiro", "operations": [{ "action": "ADD_ITEM", "name": "Pacote de Aventureiro", "query": "items/name == 'Pacote de aventureiro'" }] }
	]
}
```

#### Fazendo Consultas:
- `REQUEST`: Executa uma query no banco de dados. Muito utilizado para popular as opções de um `CHOOSE`.
```json
{"action": "REQUEST", "query": "items/metadata.type == 'weapon' AND metadata.category == 'simple' AND metadata.melee == true/name"},
```

#### Adicionando os Resultados:
- `IMPORT`: Traz operações de outra entidade para o contexto atual (ex: Subclasse importando features).
```json
{ "action": "IMPORT", "query": "subclasses/name = properties.paladin_subclass/level_3" }
```

## 4. Sintaxe de Fórmulas e Queries
### 4.1. Fórmulas
Strings que são avaliadas matematicamente. Suportam acesso a propriedades aninhadas.
- **Sintaxe:** `valor + {caminho.para.var} * floor(nível / 2)`
	- Variáveis ficam sempre entre chaves e os valores devem estar separados por espaços.
- **Contexto:** Todo o objeto do personagem está disponível (attributes, levels, proficiency_bonus).

### 4.2. Queries (Database)
Utilizadas em `REQUEST` e `IMPORT`.
- **Formato:** `collection/filtro1 AND filtro2/campo_retorno`
- **Exemplo:** `items/metadata.type == 'weapon' AND metadata.category == 'martial'/name`

## 5. Padronização de Chaves (Glossário)
Para evitar erros, o sistema utiliza internamente chaves em Inglês (snake_case).
- **Atributos:** `str`, `dex`, `con`, `int`, `wis`, `cha`
- **Recursos:** `short_rest`, `long_rest`, `nevar`
- **Categorias:** `armor`, `weapon`, `tool`, `skill`, `saving_throw`
- **Propriedades Globais:**
    - `attributes.{attr}.score`
    - `attributes.{attr}.modifier`
    - `attributes.{attr}.save` (bônus total)
    - `properties.level.{class_name}`
    - `properties.proficiency_bonus`
    - `properties.ac` (Armor Class)