import json
from typing import TYPE_CHECKING, Any, Dict, List

from .utils import get_nested, interpolate_and_eval, resolve_value, set_nested

if TYPE_CHECKING:
    from .character import Character  # Import apenas para tipagem estática


class Operation:
    def __init__(self, **kwargs: dict[str, Any]):
        if "personagem" in kwargs:
            self.personagem: "Character" = kwargs.pop("personagem")
        for key, value in kwargs.items():
            setattr(self, key, value)

    def run(self):
        pass


# --- OPERAÇÕES QUE PAUSAM ---
class InputOperation(Operation):
    property: str

    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        n = self.personagem.n

        if n >= len(decisions):
            return {"label": self.property, "options": None, "type": "input"}

        valor = decisions[n]
        set_nested(self.personagem.data, self.property, valor)
        self.personagem.n += 1
        return 1


class ChooseMapOperation(Operation):
    n: int = 1
    label: str = ""
    options: Any = []
    operations: List[Dict] = []

    def _resolve_options(self):
        # print(f"zzzzzz {self.options}")
        if isinstance(self.options, list):
            return self.options
        elif isinstance(self.options, dict) and self.options.get("action") == "REQUEST":
            # print(f"zzzzzz {self.options}")
            query = self.options.get("query")
            result = self.personagem.db.query(query)
            if isinstance(result, dict):
                return list(result.keys())
            # print(f"yyyyyy {result}")
            return result
        return []

    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        idx = self.personagem.n

        if idx >= len(decisions):
            # print(f"zzzzzz {self.options}")
            opcoes = self._resolve_options()
            return {"label": self.label, "options": opcoes, "n": self.n}

        escolha = decisions[idx]
        # Se n > 1, espera-se que a escolha seja uma lista de n itens
        itens_escolhidos = escolha if isinstance(escolha, list) else [escolha]

        novas_ops = []
        for item in itens_escolhidos:
            for op_template in self.operations:
                op_str = json.dumps(op_template).replace("{THIS}", str(item))
                novas_ops.append(json.loads(op_str))

        for op in reversed(novas_ops):
            self.personagem.ficha.insert(0, op)
        self.personagem.n += 1
        return 1


class ChooseOperationsOperation(Operation):
    n: int = 1
    label: str = ""
    options: list[Dict[str, Any]] = []

    def run(self):
        decisions = self.personagem.data.get("decisions", [])
        idx = self.personagem.n
        options = [opt.get("label") for opt in self.options]

        if idx >= len(decisions):
            return {"label": self.label, "options": options, "n": self.n}

        escolha_label = decisions[idx]
        chosen_opt = next(
            (opt for opt in self.options if opt["label"] == escolha_label), None
        )

        if chosen_opt:
            novas_ops = chosen_opt.get("operations", [])
            for op in reversed(novas_ops):
                self.personagem.ficha.insert(0, op)
        self.personagem.n += 1
        return 1


class SetOperation(Operation):
    property: str
    type: str = "value"
    value: Any = None
    formula: str = None
    recoversOn: str = "never"

    def run(self):
        if self.type == "value":
            if self.formula is not None:
                formula_str = self.formula

                def computed_property(context):
                    return interpolate_and_eval(formula_str, context)

                set_nested(self.personagem.data, self.property, computed_property)
            else:
                set_nested(self.personagem.data, self.property, self.value)
        elif self.type == "counter":
            _used = f"{self.property}_used"
            _recover = f"{self.property}_recover"
            set_nested(self.personagem.data, _recover, self.recoversOn)
            if self.formula is not None:
                formula_str = self.formula

                def computed_property(context):
                    return interpolate_and_eval(formula_str, context)

                set_nested(self.personagem.data, _used, 0)
                set_nested(self.personagem.data, self.property, computed_property)
            else:
                set_nested(self.personagem.data, _used, 0)
                set_nested(self.personagem.data, self.property, self.value)
        elif self.type == "list":
            # Lógica de lista corrigida: append/extend seguro
            current_val = get_nested(self.personagem.data, self.property)
            lista_atual = current_val if isinstance(current_val, list) else []
            novos_valores = self.value if isinstance(self.value, list) else [self.value]
            lista_atual.extend(novos_valores)
            set_nested(self.personagem.data, self.property, lista_atual)

        return 1


class IncrementOperation(Operation):
    property: str
    type: str = ""
    value: int = 1
    formula: str = None
    recoversOn: str = "never"

    def run(self):
        # 1. Busca o valor atual de forma segura
        curr_obj = get_nested(self.personagem.data, self.property)

        # 2. Se não existe, cria (delegando para SetOperation)
        if curr_obj is None:
            # Se não tem tipo definido, assume valor simples (0) + incremento
            if self.type == "":
                # Caso de uso: incremento de valor bruto que não existia (ex: atributos se não iniciados)
                set_nested(self.personagem.data, self.property, self.value)
            else:
                # Caso de uso: criar lista ou counter
                op = SetOperation(
                    personagem=self.personagem,
                    property=self.property,
                    type=self.type,
                    value=self.value,
                    formula=self.formula,
                    recoversOn=self.recoversOn,
                )
                op.run()
        else:
            # 3. Se existe, incrementa
            if not callable(curr_obj) and self.formula is None:
                if isinstance(curr_obj, (int, float)):
                    new_val = curr_obj + self.value
                    set_nested(self.personagem.data, self.property, new_val)
                elif isinstance(curr_obj, list):
                    # Incremento em lista = adicionar item
                    op = SetOperation(
                        personagem=self.personagem,
                        property=self.property,
                        type="list",
                        value=self.value,
                    )
                    op.run()

            elif callable(curr_obj) and self.formula is None:

                def computed_property(context):
                    return curr_obj(context) + self.value

                set_nested(self.personagem.data, self.property, computed_property)

            elif not callable(curr_obj) and self.formula is not None:
                formula_str = self.formula

                def computed_property(context):
                    return curr_obj + interpolate_and_eval(formula_str, context)

                set_nested(self.personagem.data, self.property, computed_property)
            else:
                formula_str = self.formula

                def computed_property(context):
                    return curr_obj(context) + interpolate_and_eval(
                        formula_str, context
                    )

                set_nested(self.personagem.data, self.property, computed_property)

        return 1


class InitOperation(SetOperation):
    def run(self):
        if get_nested(self.personagem.data, self.property) is None:
            super().run()
        return 1


class ImportOperation(Operation):
    query: str

    def run(self):
        entidade = self.personagem.db.query(self.query)
        novas_ops = entidade.get("operations", [])
        if novas_ops:
            self.personagem.ficha.extend(novas_ops)
        return 1


class ForEachOperation(Operation):
    list: List[str]
    operations: List[Dict]

    def run(self):
        items = self.list
        if isinstance(items, str):
            items = interpolate_and_eval(items, self.personagem.data)
            if not isinstance(items, list):
                items = []

        novas_ops = []
        for item in items:
            for op_template in self.operations:
                op_str = json.dumps(op_template).replace("{THIS}", str(item))
                novas_ops.append(json.loads(op_str))

        for op in reversed(novas_ops):
            self.personagem.ficha.insert(0, op)
        return 1


class InitProficiencyOperation(Operation):
    category: str
    name: str
    attributes: str = None
    multiplier: int = 0
    roll: str = "N"

    def run(self):
        nome = interpolate_and_eval(self.name, self.personagem.data)
        path = f"proficiency.{self.category}.{nome}"

        prof_data = {
            "attribute": self.attributes,
            "multiplier": self.multiplier,
            "roll": self.roll,
        }
        set_nested(self.personagem.data, path, prof_data)

        cat_cap = self.category
        name_cap = nome

        # Função reativa para calcular o bônus
        def computed_bonus(context):
            # 1. Recupera o objeto da perícia atual do contexto (para pegar multiplier atualizado)
            p_data = get_nested(context, f"proficiency.{cat_cap}.{name_cap}")
            if not p_data:
                return 0

            # 2. Descobre qual atributo usar e qual o multiplicador atual
            attr_key = p_data.get("attribute")
            mult = p_data.get("multiplier", 0)

            # 3. Busca o modificador do atributo (resolvendo recursivamente se for função)
            attr_mod = 0
            if attr_key:
                raw_mod = get_nested(context, f"attributes.{attr_key}.modifier")
                attr_mod = resolve_value(raw_mod, context)

            # 4. Busca o bônus de proficiência global
            pb = resolve_value(get_nested(context, "properties.proficiency"), context)

            # 5. Calcula: Mod + (PB * Multiplier)
            try:
                return int(int(attr_mod) + (int(pb) * float(mult)))
            except (ValueError, TypeError):
                return 0

        # Salva a função de bônus no caminho .bonus
        set_nested(self.personagem.data, f"{path}.bonus", computed_bonus)

        return 1


class AddItemOperation(Operation):
    name: str = None
    query: str
    amount: int = 1

    def run(self):
        # 1. Busca o item no Banco de Dados
        result = self.personagem.db.query(self.query)

        if not result:
            print(f"(X) Item não encontrado para query: {self.query}")
            return 1

        # CORREÇÃO: Detecta se o resultado é o dado do item direto ou um dicionário de itens
        # Se 'metadata' é uma chave direta, então `result` já é o item (Query direta: items/Escudo)
        if "metadata" in result:
            item_data = result
            # Se não temos um nome definido, tentamos deduzir da query
            item_key = self.name if self.name else self.query.split("/")[-1]
        else:
            # Caso contrário, é um resultado de busca/filtro (Query: items/type == armor)
            # Retorna { "NomeItem": {dados}, ... }
            item_key = list(result.keys())[0]
            item_data = result[item_key]

        # 2. Define o nome de exibição (Nickname ou Original)
        display_name = self.name if self.name else item_key

        # 3. Adiciona ao Inventário
        path = f"inventory.{display_name}"
        existing_item = get_nested(self.personagem.data, path)

        final_amount = self.amount
        if existing_item:
            final_amount += existing_item.get("amount", 0)

        # Cria a cópia do item para o inventário
        inventory_item = item_data.copy()
        inventory_item["amount"] = final_amount

        # Limpa operações do item salvo no inventário para não duplicar lógica ao salvar o JSON do char
        if "operations" in inventory_item:
            del inventory_item["operations"]

        set_nested(self.personagem.data, path, inventory_item)

        # 4. Injeta as Operações do Item na Fila
        # Agora item_data está correto, então ele vai encontrar as operations
        if "operations" in item_data:
            ops = item_data["operations"]
            # Inserimos no início da fila (ordem reversa) para execução imediata
            for op in reversed(ops):
                self.personagem.ficha.insert(0, op)

        return 1


class AddSpellcastingOperation(Operation):
    name: str
    can_multiclass: bool = False
    multiclass_formula: str = ""
    spellcasting_modifier: str = (
        ""  # Note: typo 'spellcastig' in some jsons, supporting standard
    )
    spell_save_dc: str = ""
    spell_attack_modifier: str = ""
    spells_prepared: str = ""
    spells_known: str = ""
    spellSlotsRecoverOn: str = ""
    spellbook_query: str = ""
    spellSlots: list[list[int]] = [[0, 0, 0, 0, 0, 0, 0, 0, 0]]

    def run(self):
        ctx = self.personagem.data

        # Cria o objeto do Spellbook resolvendo as fórmulas
        spellbook_data = {
            "config": {
                "can_multiclass": self.can_multiclass,
                "multiclass_formula": self.multiclass_formula,  # String para eval futuro se necessário
                "ability_modifier": interpolate_and_eval(
                    self.spellcasting_modifier, ctx
                ),
                "save_dc": interpolate_and_eval(self.spell_save_dc, ctx),
                "attack_modifier": interpolate_and_eval(
                    self.spell_attack_modifier, ctx
                ),
                "slots_matrix": self.spellSlots,
                "recovery": self.spellSlotsRecoverOn,
                "spells_prepared_formula": self.spells_prepared,
                "spells_known_limit": self.spells_known,
            },
            "spells": [],  # Lista onde as magias serão armazenadas
        }

        # Define slots atuais baseados no nível do personagem (simplificação, idealmente calcula pelo nível da classe)
        # Aqui apenas salvamos a estrutura. O cálculo de slots disponíveis seria derivado.

        set_nested(self.personagem.data, f"spellbooks.{self.name}", spellbook_data)
        return 1


class AddSpellOperation(Operation):
    name: str
    type: str  # always_prepared, known, etc.
    spellbook: str

    def run(self):
        # 1. Verifica se o Spellbook existe
        spellbook_path = f"spellbooks.{self.spellbook}"
        if not get_nested(self.personagem.data, spellbook_path):
            print(f"(X) Spellbook '{self.spellbook}' não encontrado.")
            return 1

        # 2. Busca a magia no BD
        # Assume que a magia está na raiz de spells.json ou acessível pelo nome
        query = f"spells/{self.name}"
        result = self.personagem.db.query(query)

        if not result:
            print(f"(X) Magia '{self.name}' não encontrada.")
            return 1

        spell_content = result.get(self.name, result)

        # 3. Adiciona a magia à lista do grimório
        spell_entry = {"name": self.name, "type": self.type, "data": spell_content}

        # Recupera lista atual e adiciona
        current_spells = get_nested(self.personagem.data, f"{spellbook_path}.spells")
        if current_spells is None:
            current_spells = []

        current_spells.append(spell_entry)
        set_nested(self.personagem.data, f"{spellbook_path}.spells", current_spells)

        return 1


class AddActionOperation(Operation):
    name: str
    cost: list[dict[str, Any]] = (
        []
    )  # ex: [{"resource": "x", "amount": 1}, {"action": "action"}]
    description: str = ""
    metadata: dict = {}

    def run(self):
        action_data = {
            "name": self.name,
            "cost": self.cost,
            "description": self.description,
            "metadata": self.metadata,
        }

        # Adiciona à lista de ações disponíveis do personagem
        path = "actions"
        current_actions = get_nested(self.personagem.data, path)
        if not isinstance(current_actions, list):
            current_actions = []

        current_actions.append(action_data)
        set_nested(self.personagem.data, path, current_actions)
        return 1


class AddFeatureOperation(Operation):
    name: str
    description: str = ""
    counter: str = None
    operations: list[dict[str, Any]] = []

    def run(self):
        feature_data = {"name": self.name, "description": self.description}

        if self.counter:
            feature_data["counter"] = self.counter

        # 1. Salva a feature na lista de features do personagem
        path = "features"
        current_features = get_nested(self.personagem.data, path)
        if not isinstance(current_features, list):
            current_features = []
        current_features.append(feature_data)
        set_nested(self.personagem.data, path, current_features)

        # 2. Executa operações aninhadas (ex: Feature que dá Action ou Bonus)
        if self.operations:
            for op in reversed(self.operations):
                self.personagem.ficha.insert(0, op)

        return 1


class AbilityScoreImprovementOperation(Operation):
    def run(self):
        # Injeta a lógica de decisão no topo da fila de processamento
        self.personagem.ficha.insert(
            0,
            {
                "action": "CHOOSE_OPERATIONS",
                "n": 1,
                "label": "Aumento no Valor de Habilidade ou Talento",
                "description": "Escolha aumentar seus atributos ou adquirir um novo talento.",
                "options": [
                    {
                        "label": "+2 em um Atributo",
                        "operations": [
                            {
                                "action": "CHOOSE_MAP",
                                "n": 1,
                                "label": "Escolha 1 atributo para receber +2",
                                "options": ["str", "dex", "con", "int", "wis", "cha"],
                                "operations": [
                                    {
                                        "action": "INCREMENT",
                                        "property": "attributes.{THIS}.score",
                                        "value": 2,
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "label": "+1 em dois Atributos",
                        "operations": [
                            {
                                "action": "CHOOSE_MAP",
                                "n": 2,
                                "label": "Escolha 2 atributos para receber +1",
                                "options": ["str", "dex", "con", "int", "wis", "cha"],
                                "operations": [
                                    {
                                        "action": "INCREMENT",
                                        "property": "attributes.{THIS}.score",
                                        "value": 1,
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "label": "Talento",
                        "operations": [
                            {
                                "action": "CHOOSE_MAP",
                                "n": 1,
                                "label": "Escolha um Talento",
                                "options": {"action": "REQUEST", "query": "feats/keys"},
                                # MUDANÇA IMPORTANTE: IMPORT carrega as regras do talento (ex: Agarrador)
                                "operations": [
                                    {"action": "IMPORT", "query": "feats/{THIS}"}
                                ],
                            }
                        ],
                    },
                ],
            },
        )
        return 1


operations = {
    "INPUT": InputOperation,
    "SET": SetOperation,
    "INCREMENT": IncrementOperation,
    "CHOOSE_MAP": ChooseMapOperation,
    "CHOOSE_OPERATIONS": ChooseOperationsOperation,
    "IMPORT": ImportOperation,
    "FOR_EACH": ForEachOperation,
    "INIT_PROFICIENCY": InitProficiencyOperation,
    "ADD_ITEM": AddItemOperation,
    "ADD_SPELLCASTING": AddSpellcastingOperation,
    "ADD_SPELL": AddSpellOperation,
    "ADD_ACTION": AddActionOperation,
    "ADD_FEATURE": AddFeatureOperation,
    "Ability_Score_Improvement": AbilityScoreImprovementOperation,
}
