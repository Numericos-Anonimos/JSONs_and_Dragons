import json
import os
import shutil


def compactar_diretorio(pasta_origem, pasta_destino):
    
    # Contadores para estatísticas
    arquivos_processados = 0
    espaco_economizado_bytes = 0
    total_bytes_originais = 0 # Acumulador para o tamanho total original

    print(f"--- Iniciando compactação de '{pasta_origem}' para '{pasta_destino}' ---\n")

    for root, dirs, files in os.walk(pasta_origem):
        caminho_relativo = os.path.relpath(root, pasta_origem)
        pasta_atual_destino = os.path.join(pasta_destino, caminho_relativo)

        os.makedirs(pasta_atual_destino, exist_ok=True)

        for file in files:
            caminho_origem = os.path.join(root, file)
            caminho_final = os.path.join(pasta_atual_destino, file)

            if file.lower().endswith('.json'):
                try:
                    # Pega o tamanho original antes de qualquer coisa
                    tamanho_original = os.path.getsize(caminho_origem)
                    
                    # 1. Ler
                    with open(caminho_origem, 'r', encoding='utf-8') as f_in:
                        dados = json.load(f_in)
                    
                    # 2. Salvar compactado
                    with open(caminho_final, 'w', encoding='utf-8') as f_out:
                        json.dump(dados, f_out, separators=(',', ':'), ensure_ascii=False)
                    
                    # 3. Calcular estatísticas
                    tamanho_novo = os.path.getsize(caminho_final)
                    
                    total_bytes_originais += tamanho_original
                    espaco_economizado_bytes += (tamanho_original - tamanho_novo)
                    arquivos_processados += 1
                    
                    print(f"[OK] Compactado: {caminho_relativo}/{file}")

                except json.JSONDecodeError:
                    print(f"[ERRO] JSON inválido: {caminho_origem}")
                except Exception as e:
                    print(f"[ERRO] Falha em {file}: {e}")
            
            else:
                shutil.copy2(caminho_origem, caminho_final)
                # Opcional: print(f"[COPIA] Arquivo não-JSON: {file}")

    # --- Relatório Final ---
    mb_economizados = espaco_economizado_bytes / (1024 * 1024)
    
    # Cálculo da porcentagem (evita divisão por zero se a pasta estiver vazia)
    if total_bytes_originais > 0:
        porcentagem = (espaco_economizado_bytes / total_bytes_originais) * 100
    else:
        porcentagem = 0

    print(f"\n--- Concluído! ---")
    print(f"Arquivos JSON processados: {arquivos_processados}")
    print(f"Espaço economizado: {mb_economizados:.2f} MB")
    print(f"Redução de tamanho: {porcentagem:.2f}%")

# --- Configuração ---
if __name__ == "__main__":
    # Defina os nomes das pastas aqui
    PASTA_ENTRADA = "BD_Legível"
    PASTA_SAIDA = "BD"

    # Verifica se a pasta de origem existe antes de começar
    if os.path.exists(PASTA_ENTRADA):
        compactar_diretorio(PASTA_ENTRADA, PASTA_SAIDA)
    else:
        print(f"A pasta '{PASTA_ENTRADA}' não foi encontrada.")
