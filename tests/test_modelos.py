from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from radar.modelos import LIMITE_TEXTO, Item, gerar_id_unico, normalizar_url


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("https://Exemplo.COM/post?utm_source=x&utm_medium=y", "https://exemplo.com/post"),
        ("https://exemplo.com/post#comentarios", "https://exemplo.com/post"),
        ("https://exemplo.com/post?b=2&a=1", "https://exemplo.com/post?a=1&b=2"),
        ("  https://exemplo.com  ", "https://exemplo.com/"),
        ("https://exemplo.com/p?id=7&UTM_Campaign=z", "https://exemplo.com/p?id=7"),
    ],
)
def test_normalizar_url(entrada: str, esperado: str) -> None:
    assert normalizar_url(entrada) == esperado


def test_variacoes_da_mesma_url_geram_mesmo_id() -> None:
    a = gerar_id_unico("https://exemplo.com/post?utm_source=rss")
    b = gerar_id_unico("https://EXEMPLO.com/post#topo")
    assert a == b
    assert len(a) == 64


def test_urls_diferentes_geram_ids_diferentes() -> None:
    assert gerar_id_unico("https://exemplo.com/a") != gerar_id_unico("https://exemplo.com/b")


def _item(**extra: object) -> Item:
    dados: dict[str, object] = {
        "modulo": "noticias",
        "fonte": "teste",
        "titulo": "Título",
        "url": "https://exemplo.com/a?utm_source=x",
    }
    dados.update(extra)
    return Item.model_validate(dados)


def test_item_calcula_id_unico_automaticamente() -> None:
    assert _item().id_unico == gerar_id_unico("https://exemplo.com/a")


def test_item_trunca_texto() -> None:
    assert len(_item(texto="x" * (LIMITE_TEXTO + 500)).texto) == LIMITE_TEXTO


def test_item_assume_utc_em_data_sem_fuso() -> None:
    item = _item(publicado_em=datetime(2026, 1, 2, 3, 4))
    assert item.publicado_em == datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def test_item_rejeita_modulo_invalido() -> None:
    with pytest.raises(ValidationError):
        _item(modulo="esportes")


def test_item_rejeita_titulo_vazio() -> None:
    with pytest.raises(ValidationError):
        _item(titulo="   ")


def test_para_banco_serializa_datas_em_iso() -> None:
    dados = _item(publicado_em=datetime(2026, 1, 2, tzinfo=UTC)).para_banco()
    assert dados["publicado_em"] == "2026-01-02T00:00:00Z"
    assert set(dados) == {"modulo", "fonte", "titulo", "url", "publicado_em", "texto", "id_unico"}
