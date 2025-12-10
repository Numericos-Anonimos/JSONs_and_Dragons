from typing import Any, Dict, List

from Api.gdrive import ensure_path, get_file_content

from .utils import get_nested

# Configuração
ROOT_FOLDER = "JSONs_and_Dragons"
DB_FOLDER = "BD"


class db_homebrew:
    def __init__(self, endereço: str, access_token: str):
        self.endereço = endereço
        self.token = access_token
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

    def query(self, query: str) -> Dict[str, Any]:
        parts = query.split("/")
        filename = f"{parts[0]}.json"

        # Silencia erro de arquivo não encontrado na API se não existir
        # (Assumindo que get_file_content já trata e retorna None)
        current_data = get_file_content(
            self.token, filename=filename, parent_id=self.folder_id
        )
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
    def __init__(self, access_token: str):
        self.token = access_token
        bd_root_id = ensure_path(self.token, [ROOT_FOLDER, DB_FOLDER])
        meta_content = get_file_content(
            self.token, filename="metadata.json", parent_id=bd_root_id
        )
        list_endereços = meta_content.get("modules", []) if meta_content else []
        self.db_list = []
        for endereço in list_endereços:
            self.db_list.append(db_homebrew(endereço, self.token))

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
