<h1 align="center"> 🛠️ Documentação Técnica do Banco de Dados 🛠️ </h1>

Esta documentação descreve a arquitetura, estrutura de dados e a linguagem de operações (DSL) utilizada para processar a criação e evolução de personagens. O sistema é agnóstico ao conteúdo, carregando regras dinamicamente através de módulos JSON.
## 1. 🏗️ Arquitetura do Sistema
O sistema opera sob um modelo de **Fila de Operações**. O `Character` (Personagem) não é apenas um objeto de dados estático, mas um processador de estado.
1. **O Banco de Dados (Modules):** O sistema carrega múltiplos módulos (ex: `dnd_2014`, `xanatar_guide`) definidos em um `metadata.json` central.
2. **A Fila (Queue):** Quando uma entidade (Raça, Classe, Item) é carregada, suas `operations` são adicionadas a uma fila de execução.
3. **O Parser:** O parser itera sobre essa fila. Se uma operação requer uma decisão do usuário (ex: Escolher uma Perícia), a execução **pausa** e aguarda uma entrada na lista de `decisions`.
4. **Mutação de Estado:** As operações modificam o dicionário `self.data` do personagem, que contém atributos, inventário, proficiências, etc.
## 2. 📂 Estrutura de Dados (Schemas)
O Banco de Dados é organizado em pastas (Módulos). Cada arquivo JSON representa uma categoria de entidades.
### 2.1. O Objeto Entidade
Toda chave raiz em um JSON (exceto metadados de arquivo) é um ID único de entidade.
```json
"Nome da Entidade": {
    "metadata": {
        "type": "string",       // ex: "weapon", "spell", "race"
        "category": "string",   // ex: "Simples", "Marcial"
        "price": number,        // Opcional
        "requirements": {}      // Opcional: Lógica de pré-requisitos
    },
    "description": "Texto descritivo ou Markdown",
    "operations": []            // Lista de comandos a executar no personagem
}
```
### 2.2. Interpolação de Variáveis `{}`
O parser suporta interpolação de strings e avaliação matemática dinâmica. Qualquer string entre chaves `{caminho.da.variavel}` é resolvida contra o estado atual do personagem.
- **Exemplo:** `"formula": "10 + {attributes.dex.modifier}"`
- **Funções Suportadas:** `floor`, `ceil`, `max`, `min`, `abs`.
## 3. ⚡ Referência de Operações (DSL)
As operações são objetos JSON dentro da lista `operations`. Abaixo estão todas as ações suportadas pelo `parser.py`.
### 🟢 Manipulação de Variáveis
#### `SET`
Define um valor em um caminho específico. Pode ser um valor fixo, uma fórmula matemática ou uma lista.
- **Parâmetros Obrigatórios:** `property`, `value` (ou `formula`).
- **Parâmetros Opcionais:** `type` ("value", "counter", "list"), `recoversOn` (para counters).
- **Como o Parser avalia:** Cria ou sobrescreve a chave no dicionário do personagem. Se for fórmula, salva uma função lambda para recálculo dinâmico.
```json
{ "action": "SET", "property": "attributes.str.score", "value": 15 }
{ "action": "SET", "property": "resources.ki", "type": "counter", "formula": "{properties.level}", "recoversOn": "short_rest" }
```
#### `INCREMENT`
Soma um valor a uma propriedade numérica existente.
- **Parâmetros Obrigatórios:** `property`.
- **Parâmetros Opcionais:** `value` (padrão 1), `formula`.
- **Como o Parser avalia:** Busca o valor atual e soma. Se não existir, age como `SET`.
```json
{ "action": "INCREMENT", "property": "attributes.dex.score", "value": 2 }
```
#### `INIT`
Inicializa uma variável apenas se ela ainda não existir. Útil para recursos que várias classes podem conceder, evitando sobrescrita.
- **Parâmetros:** Idênticos ao `SET`.
```json
{ "action": "INIT", "property": "resources.channel_divinity", "value": 1 }
```
### 🔵 Fluxo de Controle e Decisões
Estas operações podem **pausar** o parser se a lista de `decisions` do personagem não tiver dados suficientes.
#### `INPUT`
Solicita um valor bruto ao usuário (texto ou número).
- **Parâmetros Obrigatórios:** `property` (Onde salvar o input).
- **Como o Parser avalia:** Consome um item da lista de decisões e salva em `property`.
```json
{ "action": "INPUT", "property": "personal.name" }
```
#### `CHOOSE_MAP`
O usuário escolhe opções de uma lista. A escolha é injetada em operações subsequentes substituindo a tag `{THIS}`.
- **Parâmetros Obrigatórios:** `label`, `options` (Lista ou Query), `operations`.
- **Parâmetros Opcionais:** `n` (Número de escolhas, padrão 1).
- **Como o Parser avalia:**
    1. Resolve `options` (pode ser uma lista fixa ou um `REQUEST` ao BD).
    2. Pausa se não houver decisão.
    3. Pega a decisão, substitui `{THIS}` nas `operations` filhas e as injeta no **topo** da fila de execução.
```json
{
    "action": "CHOOSE_MAP", "n": 2, "label": "Escolha duas Perícias",
    "options": ["Atletismo", "Furtividade", "Intuição"],
    "operations": [{ "action": "SET", "property": "proficiency.skill.{THIS}.multiplier", "value": 1 }]
}
```
#### `CHOOSE_OPERATIONS`
O usuário escolhe entre pacotes de operações pré-definidos (comum em Equipamento Inicial).
- **Parâmetros Obrigatórios:** `label`, `options` (Lista de objetos com `label` e `operations`).
- **Como o Parser avalia:** Baseado na label escolhida, injeta as operações correspondentes na fila.
```json
{
    "action": "CHOOSE_OPERATIONS", "label": "Equipamento Inicial",
    "options": [
        { "label": "Espada e Escudo", "operations": [...] },
        { "label": "Dois Machados", "operations": [...] }
    ]
}
```
#### `FOR_EACH`
Itera sobre uma lista e executa operações para cada item.
- **Parâmetros Obrigatórios:** `list` (Array de strings), `operations`.
- **Como o Parser avalia:** Funciona como um `CHOOSE_MAP` automático que seleciona todos os itens da lista, substituindo `{THIS}`.
```json
{
    "action": "FOR_EACH", "list": ["str", "dex", "con"],
    "operations": [{ "action": "SET", "property": "attributes.{THIS}.save_prof", "value": 1 }]
}
```
### 🟠 Gerenciamento de Conteúdo
#### `IMPORT`
Carrega todas as operações de outra entidade para a fila atual.
- **Parâmetros Obrigatórios:** `query`.
- **Como o Parser avalia:** Busca a entidade no BD e adiciona suas `operations` ao final da fila (ou topo, dependendo da implementação da fila, no código atual é `extend`).
```json
{ "action": "IMPORT", "query": "classes/Paladino/level_1" }
```
#### `REQUEST` (Helper)
Não é uma operação direta da fila, mas usada dentro de `options` em `CHOOSE_MAP`. Realiza consultas ao BD.
- **Sintaxe da Query:** `arquivo/filtro1/filtro2/retorno`
    - `filtro`: Pode usar `==`, `in`, `AND`.
    - `retorno`: `keys` (retorna lista de nomes) ou nome do campo.
```json
"options": { "action": "REQUEST", "query": "items/metadata.type == 'weapon' AND metadata.category == 'Marcial'/keys" }
```
### 🟣 Proficiências e Combate
#### `INIT_PROFICIENCY`
Configura uma proficiência (Perícia, Arma, Armadura).
- **Parâmetros Obrigatórios:** `category`, `name`.
- **Parâmetros Opcionais:** `attributes` (ex: "str"), `multiplier` (0, 0.5, 1, 2), `roll` ("N", "D", "V").
- **Como o Parser avalia:** Cria um objeto complexo e uma função dinâmica `.bonus` que calcula: `Modificador Atributo + (Bônus Proficiência * Multiplicador)`.
```json
{ "action": "INIT_PROFICIENCY", "category": "skill", "name": "Atletismo", "attributes": "str", "multiplier": 1 }
```
#### `ADD_ACTION`
Adiciona uma habilidade ativa à lista de ações do personagem.
- **Parâmetros Obrigatórios:** `name`.
- **Parâmetros Opcionais:** `cost` (lista de recursos/ações gastos), `description`, `metadata`.
```json
{ "action": "ADD_ACTION", "name": "Ataque Extra", "cost": [{"action": "action"}] }
```
#### `ADD_FEATURE`
Adiciona uma característica passiva ou descritiva.
- **Parâmetros Obrigatórios:** `name`.
- **Parâmetros Opcionais:** `description`, `operations` (operações aninhadas que rodam imediatamente).
```json
{ "action": "ADD_FEATURE", "name": "Visão no Escuro", "description": "Enxerga 18m no escuro." }
```
### 🎒 Itens e Magias
#### `ADD_ITEM`
Adiciona um item ao inventário e executa suas operações passivas.
- **Parâmetros Obrigatórios:** `query`.
- **Parâmetros Opcionais:** `amount`, `name` (para renomear/apelidar).
- **Como o Parser avalia:** Busca o item, calcula quantidade (soma se já existir), e injeta as `operations` do item (ex: item mágico dando bônus) na fila do personagem.
```json
{ "action": "ADD_ITEM", "query": "items/Poção de Cura", "amount": 5 }
```
#### `ADD_SPELLCASTING`
Define as regras de conjuração de uma classe.
- **Parâmetros Principais:** `name` (Classe), `spellcasting_modifier` (Atributo), `spellSlots` (Matriz de slots por nível).
- **Como o Parser avalia:** Cria a estrutura `spellbooks.{Classe}` com slots, CD e Ataque Mágico calculados dinamicamente.
```json
{ "action": "ADD_SPELLCASTING", "name": "Mago", "spellcasting_modifier": "{attributes.int.modifier}", ... }
```
#### `ADD_SPELL`
Adiciona uma magia a um grimório existente.
- **Parâmetros Obrigatórios:** `name`, `spellbook`, `type` (known, prepared, always_prepared). 
```json
{ "action": "ADD_SPELL", "name": "Mísseis Mágicos", "spellbook": "Mago", "type": "prepared" }
```
### 🌟 Macros Especiais
#### `Ability_Score_Improvement`
Uma macro hardcoded no parser (`parser.py`) que injeta automaticamente a lógica de escolha do Nível 4+:
1. Aumentar 1 atributo em +2.
2. Aumentar 2 atributos em +1.
3. Escolher um Talento (Lê do arquivo `feats.json`).
```json
{ "action": "Ability_Score_Improvement" }
```
## 4. Glossário de Caminhos (Paths)
Para manter a consistência nas fórmulas e referências:

| Caminho                      | Descrição                 | Exemplo de Uso             |
| ---------------------------- | ------------------------- | -------------------------- |
| `attributes.{attr}.score`    | Valor bruto do atributo   | `attributes.str.score`     |
| `attributes.{attr}.modifier` | Modificador (-5 a +10)    | `attributes.dex.modifier`  |
| `properties.level`           | Nível total do personagem | `{properties.level}`       |
| `properties.proficiency`     | Bônus de Proficiência     | `{properties.proficiency}` |
| `properties.ac`              | Classe de Armadura        | `properties.ac`            |
| `personal.race`              | Raça definida             | `personal.race`            |
| `inventory.{item_name}`      | Acesso a itens            | `inventory.Espada Longa`   |
