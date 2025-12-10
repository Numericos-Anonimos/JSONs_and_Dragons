import json
import os
from typing import Any, Dict, List

from Api.gdrive import ensure_path, get_file_content

from .utils import get_nested

# Configuração
ROOT_FOLDER = "JSONs_and_Dragons"
DB_FOLDER = "BD"


class db_homebrew:
    def __init__(
        self, endereço: str, access_token: str | None = None, use_local: bool = False
    ):
        self.endereço = endereço
        self.token = access_token
        self.use_local = use_local
        self.folder_id = None

        # Se NÃO for local, precisamos garantir que a pasta existe no Drive
        if not self.use_local and self.token:
            self.folder_id = ensure_path(
                self.token, [ROOT_FOLDER, DB_FOLDER, self.endereço]
            )

    def _check_in_filter(self, target_value: Any, expected_value: str) -> bool:
        if not target_value:
            return False
        if isinstance(target_value, list):
            return any(
                (isinstance(item, dict) and item.get("name") == expected_value)
                or (isinstance(item, str) and item == expected_value)
                for item in target_value
            )
        if isinstance(target_value, str):
            return target_value == expected_value
        return False

    def _apply_filter(self, data: Dict[str, Any], filter_str: str) -> Dict[str, Any]:
        if " AND " in filter_str:
            subparts = filter_str.split(" AND ")
            filtered_data = data
            for subpart in subparts:
                filtered_data = self._apply_filter(filtered_data, subpart.strip())
            return filtered_data
        elif " == " in filter_str:
            path, expected_value_raw = filter_str.split(" == ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            return {
                key: value
                for key, value in data.items()
                if str(get_nested(value, path.strip())) == expected_value
            }
        elif " in " in filter_str:
            expected_value_raw, path_raw = filter_str.split(" in ", 1)
            expected_value = expected_value_raw.strip().strip("'")
            return {
                key: value
                for key, value in data.items()
                if self._check_in_filter(
                    get_nested(value, path_raw.strip()), expected_value
                )
            }
        return data

    def query_parts(self, part: str, dados: Dict[str, Any]) -> Dict[str, Any]:
        if "==" in part or " in " in part:
            parts = part.rsplit("/", 1)
            filter_only = parts[0]
            return_field = parts[1] if len(parts) > 1 else None
            filtered_data = self._apply_filter(dados, filter_only)
            if return_field == "keys":
                return {key: key for key in filtered_data.keys()}
            if return_field:
                return {
                    key: get_nested(value, return_field.strip())
                    for key, value in filtered_data.items()
                    if get_nested(value, return_field.strip()) is not None
                }
            return filtered_data
        return dados.get(part, {})

    def _fetch_content(self, filename: str) -> Dict[str, Any]:
        """Método helper para abstrair a fonte do dado (Local vs Drive)"""

        # --- MODO LOCAL ---
        if self.use_local:
            # Assume que a pasta BD está na raiz do projeto ou no diretório de execução
            # Caminho: ./BD/{endereço}/{filename}
            local_path = os.path.join(DB_FOLDER, self.endereço, filename)

            # Tenta buscar, se não achar retorna vazio (igual ao comportamento da API)
            if not os.path.exists(local_path):
                # Fallback: Tentar achar em relação ao arquivo atual se o path relativo falhar
                base_dir = os.path.dirname(
                    os.path.abspath(__file__)
                )  # jsons_and_dragons/
                root_dir = os.path.dirname(base_dir)  # Raiz do projeto
                local_path = os.path.join(root_dir, DB_FOLDER, self.endereço, filename)

            if os.path.exists(local_path):
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Erro ao ler arquivo local {local_path}: {e}")
                    return {}
            return {}

        # --- MODO DRIVE ---
        return get_file_content(self.token, filename=filename, parent_id=self.folder_id)

    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        filename = f"{parts[0]}.json"

        # Usa o helper para pegar o conteúdo (seja do Drive ou Local)
        current_data = self._fetch_content(filename)

        if not current_data:
            return {}

        for i in range(1, len(parts)):
            part = parts[i]
            if part == "keys":
                return list(current_data.keys())
            current_data = self.query_parts(part, current_data)
            if not current_data and i < len(parts) - 1:
                return {}
        return current_data if isinstance(current_data, dict) else {}


class db_handler(db_homebrew):
    def __init__(self, access_token: str = None, use_local: bool = False):
        self.token = access_token
        self.use_local = use_local
        self.db_list = []

        list_endereços = []

        if self.use_local:
            # Lógica Local: Lê metadata.json direto do disco
            local_meta_path = os.path.join(DB_FOLDER, "metadata.json")
            if not os.path.exists(local_meta_path):
                # Fallback de caminho
                base_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.dirname(base_dir)
                local_meta_path = os.path.join(root_dir, DB_FOLDER, "metadata.json")

            if os.path.exists(local_meta_path):
                with open(local_meta_path, "r", encoding="utf-8") as f:
                    meta_content = json.load(f)
                    list_endereços = meta_content.get("modules", [])
        else:
            # Lógica Drive: Busca via API
            bd_root_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER])
            meta_content = get_file_content(
                self.token, filename="metadata.json", parent_id=bd_root_id
            )
            list_endereços = meta_content.get("modules", []) if meta_content else []

        # Instancia os sub-bancos propagando a flag use_local
        for endereço in list_endereços:
            self.db_list.append(
                db_homebrew(endereço, self.token, use_local=self.use_local)
            )

    def query(self, query: str):
        response = {}
        for db in self.db_list:
            resultado_parcial = db.query(query)
            if resultado_parcial:
                if not response:
                    response = (
                        resultado_parcial.copy()
                        if isinstance(resultado_parcial, dict)
                        else list(resultado_parcial)
                    )
                    continue
                if isinstance(response, dict) and isinstance(resultado_parcial, dict):
                    for k, v in resultado_parcial.items():
                        # Lógica de merge para não perder operações
                        if (
                            k == "operations"
                            and isinstance(v, list)
                            and "operations" in response
                            and isinstance(response["operations"], list)
                        ):
                            response["operations"].extend(v)
                        else:
                            response[k] = v
                elif isinstance(response, list) and isinstance(resultado_parcial, list):
                    response.extend(resultado_parcial)
        return response
