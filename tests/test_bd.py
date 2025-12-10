import pytest

from jsons_and_dragons import db_handler


# Fixture: Prepara o ambiente antes do teste (instancia o DB)
@pytest.fixture
def db_local():
    """Retorna uma instância do db_handler configurada para uso local."""
    return db_handler(use_local=True)


def test_deve_listar_classes_do_bd_local(db_local):
    """
    Verifica se consegue ler o arquivo classes.json localmente
    e se as classes principais estão presentes.
    """
    # Ação
    resultado = db_local.query("classes/keys")

    # Asserções (Validações)
    assert resultado is not None, "O resultado da query não deveria ser None"
    assert len(resultado) > 0, "A lista de classes não deveria estar vazia"

    # Verifica se as classes esperadas estão na lista
    assert "Paladino" in resultado
    assert "Bárbaro" in resultado


def test_deve_retornar_vazio_para_caminho_invalido(db_local):
    """
    Garante que o sistema não quebra (e retorna vazio) ao buscar algo que não existe.
    """
    resultado = db_local.query("arquivo_inexistente/keys")
    # Baseado na sua implementação, deve retornar dict ou lista vazia
    assert not resultado
