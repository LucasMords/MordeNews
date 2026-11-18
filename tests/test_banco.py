import json
from datetime import UTC, datetime

import pytest

from radar import banco
from radar.modelos import Item
from tests.conftest import SupabaseFalso


def _item(url: str = "https://exemplo.com/a", titulo: str = "Título") -> Item:
    return Item(modulo="noticias", fonte="teste", titulo=titulo, url=url, texto="corpo")


def test_cabecalhos_chave_nova_nao_vai_no_authorization() -> None:
    cabecalhos = banco._cabecalhos("sb_secret_abc")
    assert cabecalhos["apikey"] == "sb_secret_abc"
    assert "Authorization" not in cabecalhos


def test_cabecalhos_chave_jwt_vai_no_authorization() -> None:
    assert banco._cabecalhos("eyJhbGciOi.x.y")["Authorization"] == "Bearer eyJhbGciOi.x.y"


def test_salvar_itens_nao_duplica(supabase: SupabaseFalso) -> None:
    assert banco.salvar_itens([_item("https://exemplo.com/a"), _item("https://exemplo.com/b")]) == 2
    # mesma URL com utm_* e fragmento é o mesmo item
    assert banco.salvar_itens([_item("https://exemplo.com/a?utm_source=rss#x")]) == 0
    assert len(supabase.tabelas["itens"]) == 2


def test_salvar_itens_deduplica_dentro_do_lote(supabase: SupabaseFalso) -> None:
    assert banco.salvar_itens([_item(), _item()]) == 1
    corpo = json.loads(supabase.requisicoes[-1].content)
    assert len(corpo) == 1


def test_salvar_itens_usa_upsert_ignorando_duplicatas(supabase: SupabaseFalso) -> None:
    banco.salvar_itens([_item()])
    requisicao = supabase.requisicoes[-1]
    assert requisicao.url.params["on_conflict"] == "id_unico"
    assert "resolution=ignore-duplicates" in requisicao.headers["Prefer"]


def test_salvar_lista_vazia_nao_chama_o_banco(supabase: SupabaseFalso) -> None:
    assert banco.salvar_itens([]) == 0
    assert supabase.requisicoes == []


def test_existe_e_obter_item(supabase: SupabaseFalso) -> None:
    item = _item()
    assert not banco.existe(item.id_unico)
    banco.salvar_itens([item])
    assert banco.existe(item.id_unico)
    gravado = banco.obter_item(item.id_unico)
    assert gravado is not None
    assert gravado["titulo"] == "Título"
    assert banco.obter_item("nao-existe") is None


def test_apagar_item(supabase: SupabaseFalso) -> None:
    item = _item()
    banco.salvar_itens([item, _item("https://exemplo.com/outro")])
    banco.apagar_item(item.id_unico)
    assert not banco.existe(item.id_unico)
    assert len(supabase.tabelas["itens"]) == 1


def test_pendentes_filtra_por_modulo_e_status(supabase: SupabaseFalso) -> None:
    banco.salvar_itens([_item("https://exemplo.com/1"), _item("https://exemplo.com/2")])
    banco.salvar_itens(
        [Item(modulo="estagios", fonte="t", titulo="Vaga", url="https://vagas.com/1")]
    )
    supabase.tabelas["itens"][1]["status"] = "processado"

    resultado = banco.pendentes("noticias", limite=10)

    assert [p.url for p in resultado] == ["https://exemplo.com/1"]
    assert resultado[0].tentativas_ia == 0


def test_marcar_enviados(supabase: SupabaseFalso) -> None:
    banco.salvar_itens([_item("https://exemplo.com/1"), _item("https://exemplo.com/2")])
    banco.marcar_enviados([1])
    linhas = {linha["id"]: linha for linha in supabase.tabelas["itens"]}
    assert linhas[1].get("enviado_em")
    assert not linhas[2].get("enviado_em")


def test_marcar_enviados_vazio_nao_chama_o_banco(supabase: SupabaseFalso) -> None:
    banco.marcar_enviados([])
    assert supabase.requisicoes == []


def test_registrar_execucao(supabase: SupabaseFalso) -> None:
    inicio = datetime(2026, 1, 1, tzinfo=UTC)
    banco.registrar_execucao("rss-x", iniciado_em=inicio, ok=False, erro="E" * 5000)
    linha = supabase.tabelas["execucoes"][0]
    assert linha["coletor"] == "rss-x"
    assert linha["ok"] is False
    assert len(linha["erro"]) == 2000
    assert banco.ultimas_execucoes("rss-x")[0]["coletor"] == "rss-x"


def test_erro_http_vira_erro_banco(supabase: SupabaseFalso) -> None:
    supabase.falhar_com = 401
    with pytest.raises(banco.ErroBanco, match=r"401.*erro simulado"):
        banco.existe("x")
