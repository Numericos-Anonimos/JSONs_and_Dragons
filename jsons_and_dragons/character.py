import base64
import json
from typing import Any, List

import dill as pickle

from .data import db_handler
from .operations import operations  # Importa o dicionário de operações
from .utils import get_nested, interpolate_and_eval, resolve_value, set_nested


class Character:
    def __init__(self, id: int, access_token: str, decisions: List[Any] = None):
        self.id = id
        self.access_token = access_token
        self.db = db_handler(self.access_token)

        self.data = {
            "decisions": decisions if decisions else [],
            "proficiency": {},
            "attributes": {},
            "properties": {},
            "personal": {},
            "spellbooks": {},
            "inventory": {},
        }
        self.n = 0
        self.ficha = [{"action": "IMPORT", "query": "metadata/character"}]
        self.required_decision = None

        print(f"--- Iniciando processamento Character ID {id} ---")
        self.process_queue()

    def add_race(self):
        self.n += 1  # Consome o Raça
        race = self.data["decisions"][self.n]
        self.n += 1  # Consome o nome da raça

        print(f"-> Adicionando Raça: {race}")
        self.ficha.append({"action": "IMPORT", "query": f"races/{race}"})
        self.required_decision = None
        self.process_queue()

    def add_background(self):
        self.n += 1  # Consome o Background
        background = self.data["decisions"][self.n]
        self.n += 1  # Consome o nome do background

        print(f"-> Adicionando Background: {background}")
        self.ficha.append({"action": "IMPORT", "query": f"backgrounds/{background}"})
        self.required_decision = None
        self.process_queue()

    def add_class(self):
        self.n += 1  # Consome a Classe
        class_name = self.data["decisions"][self.n]
        self.n += 1  # Consome o nome da Classe
        level = self.data["decisions"][self.n]
        self.n += 1  # Consome o Nível

        print(f"-> Adicionando Classe: {class_name} (Nível {level})")
        self.ficha.append(
            {"action": "IMPORT", "query": f"classes/{class_name}/level_{level}"}
        )

        if level != 0:
            class_data = self.db.query(f"classes/{class_name}")
            hit_dice = class_data["hitDiceValue"]
            if self.get_stat("properties.level") == 0:  # MÁXIMO
                self.ficha.append(
                    {
                        "action": "INCREMENT",
                        "property": "properties.hit_points",
                        "value": hit_dice,
                    }
                )
            else:
                self.ficha.append(
                    {
                        "action": "CHOOSE_MAP",
                        "n": 1,
                        "label": f"Pontos de Vida (D{hit_dice})",
                        "options": [i for i in range(1, hit_dice + 1)],
                        "operations": [
                            {
                                "action": "INCREMENT",
                                "property": "properties.hit_points",
                                "formula": "{THIS}",
                            }
                        ],
                    }
                )

        self.required_decision = None
        self.process_queue()

    def process_queue(self):
        self.required_decision = {}
        while len(self.ficha) > 0:
            if self.required_decision != {}:
                # print(f"(!) Processamento pausado. Aguardando: {self.required_decision['label']}")
                break

            result = self.run_operation()

            if isinstance(result, dict):
                self.required_decision = result
                print(f"(!) Decisão Necessária detectada: {result['label']}")
                break

            if result == -1:
                print("(X) Erro fatal na operação.")
                break

        if not self.ficha and not self.required_decision:
            print("(v) Fila vazia. Processamento concluído.")

    def run_operation(self):
        if not self.ficha:
            return 1

        op_data = self.ficha.pop(0)
        op_args = op_data.copy()
        action = op_args.pop("action", None)

        print(
            f"[N={self.n}] Exec: {action} - {op_args.get('property') or op_args.get('label') or op_args.get('query') or op_args.get('name') or ''}"
        )

        op_class = operations.get(action)
        if not op_class:
            return 1

        op_instance = op_class(personagem=self, **op_args)
        result = op_instance.run()

        if isinstance(result, dict):
            # print(f"    -> Pausando em {action} (Falta decisão {self.n})")
            self.ficha.insert(0, op_data)

        return result

    def get_basic_infos(self):
        # [(Classe, Nível)] Para Multiclasses
        classes = self.data["properties"]["classes"].items()

        return {
            "id": self.id,
            "name": self.get_stat("personal.name"),
            "race": self.get_stat("personal.subrace"),
            "background": self.get_stat("personal.background"),
            "class": classes,
            "level": self.get_stat("properties.level"),
        }

    def get_all(self):
        print(f"--- Carregando ID {self.id} ---")
        # 1. Informações Básicas
        # Não tem mais

        # 2. Atributos e Salvaguardas
        stats = {}
        for attr in ["str", "dex", "con", "int", "wis", "cha"]:
            stats[attr] = {
                "score": self.get_stat(f"attributes.{attr}.score"),
                "modifier": self.get_stat(f"attributes.{attr}.modifier"),
                "save": self.get_stat(f"attributes.{attr}.save"),
            }
        print("Atributos Carregados")

        # 3. Skills
        skills = []
        proficiency_bonus = self.get_stat("properties.proficiency")
        all_skills = self.data["proficiency"].get("skill", {})
        for skill_name, data in all_skills.items():
            total_bonus = self.get_stat(f"proficiency.skill.{skill_name}.bonus")
            roll = self.get_stat(f"proficiency.skill.{skill_name}.roll")
            multiplier = self.get_stat(f"proficiency.skill.{skill_name}.multiplier")
            skills.append(
                {
                    "name": skill_name,
                    "attribute": data.get("attribute", "").upper(),
                    "multiplier": multiplier,
                    "bonus": total_bonus,
                    "roll": roll,
                }
            )
        skills.sort(key=lambda x: x["name"])
        print("Skills Carregadas")

        # 4. Combate
        combat = {
            "hp_max": self.get_stat("properties.hit_points"),
            "ac": self.get_stat("properties.ac"),
            "initiative": self.get_stat("attributes.initiative"),
            "speed": self.get_stat("attributes.speed"),
            "proficiency_bonus": proficiency_bonus,
        }
        print("Combate Carregado")

        # 5. Ataques
        attacks = []
        actions_list = self.data.get("actions", [])

        for action in actions_list:
            meta = action.get("metadata", {})
            # Verifica se é um ataque olhando as categorias ou metadados
            cats = meta.get("category", [])
            if "Ataque" in cats or "Combate" in cats:
                # As fórmulas vêm como string "1d20 + {str}..."
                # Precisamos resolver os {} usando o parser
                raw_acerto = meta.get("Acerto", "0")
                raw_dano = meta.get("Dano", "0")

                # Resolve valores dinâmicos ({attributes.str.modifier}, etc)
                val_acerto_str = interpolate_and_eval(raw_acerto, self.data)
                val_dano = interpolate_and_eval(raw_dano, self.data).replace("+ -", "-")

                # Truque: Para pegar o bônus fixo (ex: +5) de uma string "1d20 + 5",
                # podemos substituir '1d20' por '0' e avaliar a matemática.
                bonus_attack = 0
                try:
                    if isinstance(val_acerto_str, str):
                        # Remove o dado para calcular só o bônus numérico
                        formula_limpa = val_acerto_str.lower().replace("1d20", "0")
                        bonus_attack = eval(formula_limpa, {"__builtins__": None}, {})
                    else:
                        bonus_attack = val_acerto_str
                except:
                    bonus_attack = 0

                attacks.append(
                    {
                        "name": action["name"],
                        "bonus": bonus_attack,
                        "damage": f"{val_dano} {meta.get('Tipo de Dano', '')}",
                        "range": meta.get("Alcance", "-"),
                    }
                )
        print("Ataques Carregados")

        # 6. Equipamento
        inventory = []
        raw_inventory = self.data.get("inventory", {})
        for item_name, item_data in raw_inventory.items():
            if item_name == "metadata":
                continue
            inventory.append(
                {
                    "name": item_name,
                    "amount": item_data.get("amount", 1),
                    "description": item_data.get("description", ""),
                }
            )
        print("Equipamento Carregado")

        # 7. Features e Contadores
        features_list = []
        for feat in self.data.get("features", []):
            counter_val = 0
            # 'counter' no JSON da feature é o CAMINHO (ex: resources.sentido_divino)
            resource_path = feat.get("counter", None)

            if resource_path:
                print(f"Resource path: {resource_path}")
                # Precisamos buscar o valor real nesse caminho
                counter_val = self.get_stat(resource_path)

                # Se o valor é uma função lambda (comum no seu parser), get_stat já resolve.
                # Mas se o recurso não foi inicializado corretamente, pode vir None.
                if counter_val is None:
                    counter_val = 0

            features_list.append(
                {
                    "name": feat.get("name"),
                    "description": feat.get("description", "")[:100] + "...",
                    "counter": counter_val,
                }
            )
        print("Features Carregadas")

        return {
            "header": {
                "id": self.id,
                "name": self.get_stat("personal.name"),
                "race": self.get_stat("personal.subrace")
                or self.get_stat("personal.race"),
                "class_level": self.data["properties"]["classes"].items(),
                "background": self.get_stat("personal.background"),
            },
            "attributes": stats,
            "skills": skills,
            "combat": combat,
            "attacks": attacks,
            "equipment": inventory,
            "features": features_list,
        }

    def get_stat(self, path: str) -> Any:
        return resolve_value(get_nested(self.data, path), self.data)

    def update_token(self, new_token: str):
        """
        Atualiza o token de acesso da instância e do banco de dados.
        Essencial ao carregar um personagem salvo, pois o token antigo terá expirado.
        """
        self.access_token = new_token
        if self.db:
            self.db.token = new_token
            # Atualiza tokens dos sub-bancos também
            for db in self.db.db_list:
                db.token = new_token

    def to_json(self) -> str:
        """Serializa as decisões do personagem para uma string JSON"""
        return json.dumps(self.data["decisions"], indent=4, ensure_ascii=False)

    def to_pickle_string(self) -> str:
        """Serializa o personagem inteiro para uma string base64"""
        # Removemos temporariamente o required_decision para economizar espaço ou evitar recursão, se necessário
        # mas com dill geralmente é tranquilo.
        binary_data = pickle.dumps(self)
        return base64.b64encode(binary_data).decode("utf-8")

    @staticmethod
    def from_pickle_string(pickle_str: str, new_token: str) -> "Character":
        """Recria o personagem a partir da string base64 e atualiza o token"""
        binary_data = base64.b64decode(pickle_str.encode("utf-8"))
        char = pickle.loads(binary_data)
        char.update_token(new_token)
        return char


# Main =======================================================
def main():
    import os

    from dotenv import load_dotenv
    from jose import jwt

    load_dotenv()

    env_token = os.getenv("JWT_TOKEN")
    env_secret = os.getenv("JWT_SECRET")
    payload = jwt.decode(
        env_token, env_secret, algorithms=[os.getenv("JWT_ALGORITHM", "HS256")]
    )
    google_access_token = payload.get("google_access_token")

    decisoes_parciais = ["Tony Starforge", 15, 12, 14, 8, 8, 14, "Anão"]

    print("\n--- TESTE 1: Inicialização ---")
    personagem = Character(
        0, access_token=google_access_token, decisions=decisoes_parciais
    )

    print("\n--- TESTE 2: Adicionando Raça (Deve Pausar) ---")
    personagem.add_race("Humano")

    if personagem.required_decision:
        print(
            f"\n>> JSON RETORNO: {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}"
        )
    else:
        print("\n>> ERRO: Não pausou onde deveria!")

    print("\n--- TESTE 3: Retomada (Com Subraça) ---")
    personagem.data["decisions"] += ["Humano (Variante)"]
    personagem.process_queue()
    # pprint(personagem.data)

    if personagem.required_decision:
        print(
            f"\n>> JSON RETORNO (Passo 2): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}"
        )

    # O Humano Variante escolhe 2 atributos para aumentar +1. Vamos escolher Str e Cha.
    personagem.data["decisions"] += [["str", "cha"]]
    personagem.process_queue()

    # Debug: Verificar se STR aumentou (era 15)
    print(f"\nForça Final: {personagem.get_stat('attributes.str.score')}")

    if personagem.required_decision:
        print(
            f"\n>> JSON RETORNO (Passo 3): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}"
        )

    personagem.data["decisions"] += ["Arcanismo", "Agarrador"]
    personagem.process_queue()

    if personagem.required_decision:
        print(
            f"\n>> JSON RETORNO (Passo 4): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}"
        )

    personagem.process_queue()

    if personagem.required_decision:
        print(
            f"\n>> JSON RETORNO (Passo 5): {json.dumps(personagem.required_decision, indent=2, ensure_ascii=False)}"
        )
    else:
        print("\n>> Não pausou, mas agora finalizado")

    print("\n=== Teste de Bônus de Perícia ===")
    # Atletismo é STR. STR score 16 (+3). Proficiencia (nível 0 -> +2). Multiplicador 0 (inicial).
    # Bônus esperado: 3 + (2 * 0) = 3
    atletismo_bonus = personagem.get_stat("proficiency.skill.Atletismo.bonus")
    print(f"Bônus de Força: {personagem.get_stat('attributes.str.bonus')}")
    print(f"Bônus Atletismo (Base): {atletismo_bonus}")
    print(f'Bônus de Proficiência: {personagem.get_stat("properties.proficiency")}')

    print("-> Tornando proficiente em Atletismo...")
    personagem.data["proficiency"]["skill"]["Atletismo"]["multiplier"] = 1
    atletismo_bonus_novo = personagem.get_stat("proficiency.skill.Atletismo.bonus")
    print(
        f"Bônus Atletismo (Proficiente): {atletismo_bonus_novo}"
    )  # Esperado: 3 + 2 = 5

    personagem.data["decisions"] += [["Elfico", "Dracônico"], "Livro de Orações"]
    personagem.add_background("Acólito")

    print("======== Personagem Finalizado ========")
    pprint(personagem.data)


if __name__ == "__main__":
    main()
