import copy
from collections import deque


class CharacterBuilder:
    def __init__(self, db_loader):
        self.db = db_loader
        self.data = {} # A ficha sendo construída
        self.answers = {} # Respostas acumuladas { "choice_id": "valor" }
        self.pending_choices = []

    def process(self, operations, provided_answers=None):
        if provided_answers:
            self.answers.update(provided_answers)
        
        # Fila de operações a serem processadas
        # Usamos deque para poder injetar operações no início (prioridade)
        queue = deque(operations)
        
        # Limpa escolhas pendentes para recalcular
        self.pending_choices = []
        
        op_index = 0
        while queue:
            op = queue.popleft()
            op_id = f"op_{op_index}" # Simplificação, idealmente use um hash determinístico do caminho
            op_index += 1

            action = op.get("action")

            if action == "SET":
                self._apply_set(op)
            
            elif action == "INCREMENT":
                self._apply_increment(op)

            elif action == "IMPORT":
                # RESOLUÇÃO DO PROBLEMA DO PALADINO
                # Resolvemos as variáveis na query ANTES de importar
                query = self._resolve_variables(op["query"]) 
                imported_ops = self.db.fetch_operations(query)
                
                # INJEÇÃO DINÂMICA:
                # As operações importadas entram no INÍCIO da fila
                # para serem processadas imediatamente
                for new_op in reversed(imported_ops):
                    queue.appendleft(new_op)

            elif action.startswith("CHOOSE"):
                # Se já temos resposta para essa escolha
                if op_id in self.answers:
                    user_selection = self.answers[op_id]
                    
                    # Lógica para processar a escolha feita
                    # Ex: Se escolheu "Humano Variante", pega as operations dele
                    selected_ops = self._resolve_choice_consequences(op, user_selection)
                    
                    # Injeta as consequências na fila!
                    # Isso resolve o Humano Variante: ao escolher, as ops de Atributo/Talento entram na fila
                    for new_op in reversed(selected_ops):
                        queue.appendleft(new_op)
                else:
                    # Se NÃO temos resposta, adicionamos à lista de pendências
                    # E continuamos? Depende.
                    # Se for "Blocking" (necessário para um import futuro), paramos.
                    # Por segurança, em árvores complexas, geralmente coletamos o que dá e paramos.
                    choice_obj = self._build_choice_object(op_id, op)
                    self.pending_choices.append(choice_obj)
                    
                    # Opcional: Se quiser suportar múltiplas perguntas independentes, continue.
                    # Se a próxima operação depender desta, vai quebrar.
                    # Recomendação: Adicione à pendência e continue, mas se uma operação futura
                    # falhar por falta de dados (ex: IMPORT com variavel vazia), pare o loop.

        return {
            "status": "COMPLETED" if not self.pending_choices else "WAITING_FOR_INPUT",
            "sheet": self.data,
            "choices": self.pending_choices
        }

    def _resolve_choice_consequences(self, op, selection):
        # Aqui acontece a mágica do {THIS}
        # Se o usuário escolheu "Atletismo", e a operação diz:
        # "SET proficiency.{THIS}.multiplier = 1"
        # Nós geramos: "SET proficiency.Atletismo.multiplier = 1"
        
        new_ops = []
        # Lógica para extrair as 'operations' de dentro da opção escolhida (caso Equipment A)
        # OU lógica para interpolar {THIS} nas 'operations' genéricas do CHOOSE_MAP
        return new_ops