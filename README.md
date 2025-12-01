<img src="assets/banner.png" alt="Banner" width="100%">

**JSONs & Dragons** é uma API RESTful e Engine de Regras projetada para processar, validar e evoluir fichas de personagem de D&D 5ª Edição de forma programática.

O objetivo deste projeto não é ser uma interface de usuário, mas sim o **backend robusto e expansível** que alimenta VTTs, criadores de ficha, bots de Discord e ferramentas de homebrew. Ele abstrai a complexidade das regras de D&D em uma arquitetura puramente baseada em JSON.

## ⚡ Principais Funcionalidades

- **Rule Engine Agnóstica:** Toda a lógica (classes, raças, itens) é definida em arquivos JSON, não hardcoded em Python. Adicionar uma nova classe homebrew é tão simples quanto fazer upload de um arquivo.
    
- **Processamento em Fila (Queue-Based):** A criação de personagem não é linear. A API gerencia uma fila de operações e "pausa" a execução quando uma decisão do usuário é necessária (ex: escolher uma perícia ou talento).
    
- **Expansibilidade Infinita:** Suporte nativo para múltiplos módulos de conteúdo (SRD, Tasha, Xanathar, Homebrews).
    

## 🚀 Como a API Funciona

A interação com a API segue um ciclo de **Processamento -> Pausa -> Decisão**:

1. **POST `/character/create`**: O cliente inicia um personagem (ex: escolhe "Raça: Humano").
    
2. **API Processa**: Aplica os bônus de atributo base do Humano.
    
3. **API Pausa**: Encontra uma decisão pendente (ex: "Humano Variante" exige escolher um Talento).
    
4. **Response 202 (Accepted)**: Retorna o estado parcial e um objeto `required_decision` listando as opções disponíveis.
    
5. **POST `/character/{id}/decide`**: O cliente envia a escolha do usuário.
    
6. **API Retoma**: Aplica o talento escolhido e continua o processamento.
    

## 📚 Documentação Técnica

Para entender a estrutura dos JSONs de regras e a DSL (Domain Specific Language) utilizada para criar novos conteúdos (Classes, Itens, Magias), consulte a documentação detalhada:

👉 [**Documentação da Estrutura de Regras (bd_docs.md)**](BD/DocsBD.md)

## 📦 Estrutura do Repositório

- `/Api`: Código fonte dos endpoints e lógica de autenticação.
    
- `/jsons_and_dragons`: O "Core" da engine. Contém o `parser.py` e a lógica de mutação de estado.
    
- `/BD`: Diretório de dados. Aqui residem os módulos de regras (SRD, Homebrews) em formato JSON.
    
- `/tests`: Testes unitários para garantir a integridade das regras.

## 📄 Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.