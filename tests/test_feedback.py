"""Bloco 7: votos 👍/👎 do portal no prompt da triagem e links de voto no e-mail."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from radar import banco, config
from radar.entrega import correio
from radar.ia import cliente, triagem
from radar.modelos import Exemplo, Item, ItemPendente, ItemResumo, Modulo, Resultado
from tests.conftest import SupabaseFalso

AGORA = datetime(2026, 11, 21, 12, tzinfo=UTC)


def _votar(supabase: SupabaseFalso, item_id: int, voto: int, dias_atras: float = 1) -> None:
    supabase.tabelas["feedback"].append(
        {
            "id": len(supabase.tabelas["feedback"]) + 1,
            "item_id": item_id,
            "voto": voto,
            "criado_em": (AGORA - timedelta(days=dias_atras)).isoformat(),
        }
    )


def _semear(supabase: SupabaseFalso, modulo: Modulo, titulos: Sequence[str]) -> list[int]:
    banco.salvar_itens(
        Item(modulo=modulo, fonte="f", titulo=t, url=f"https://e.com/{modulo}/{n}")
        for n, t in enumerate(titulos)
    )
    linhas = [linha for linha in supabase.tabelas["itens"] if linha["modulo"] == modulo]
    for linha in linhas:
        linha["nota"] = 7
    return [linha["id"] for linha in linhas]


# ------------------------------------------------------------------ banco


def test_exemplos_do_modulo_mais_recentes_primeiro(supabase: SupabaseFalso) -> None:
    rust, java, cupom = _semear(supabase, "noticias", ["Rust 2.0", "Java 27", "Cupom de desconto"])
    [vaga] = _semear(supabase, "estagios", ["Estágio em dados"])
    _votar(supabase, java, 1, dias_atras=3)
    _votar(supabase, rust, 1, dias_atras=1)
    _votar(supabase, cupom, -1, dias_atras=2)
    _votar(supabase, vaga, 1)  # outro módulo: fica de fora
    _votar(supabase, rust, -1, dias_atras=200)  # antigo demais

    exemplos = banco.exemplos_feedback("noticias", AGORA - timedelta(days=90))

    assert [(e.titulo, e.voto, e.nota) for e in exemplos] == [
        ("Rust 2.0", 1, 7),
        ("Java 27", 1, 7),
        ("Cupom de desconto", -1, 7),
    ]


def test_exemplos_limitados_por_tipo(supabase: SupabaseFalso) -> None:
    ids = _semear(supabase, "noticias", [f"Notícia {n}" for n in range(5)])
    for n, item_id in enumerate(ids):
        _votar(supabase, item_id, 1, dias_atras=n + 1)

    exemplos = banco.exemplos_feedback("noticias", AGORA - timedelta(days=90), limite=2)

    assert [e.titulo for e in exemplos] == ["Notícia 0", "Notícia 1"]


def test_sem_votos_nao_consulta_itens(supabase: SupabaseFalso) -> None:
    assert banco.exemplos_feedback("noticias", AGORA - timedelta(days=90)) == []
    assert all("/itens" not in str(r.url) for r in supabase.requisicoes)


# ------------------------------------------------------------------ prompt


def test_secao_de_exemplos_no_prompt() -> None:
    exemplos = [
        Exemplo(titulo="Rust 2.0", voto=1, nota=6),
        Exemplo(titulo="Cupom de desconto", voto=-1, nota=None),
    ]

    instrucoes = cliente.montar_instrucoes("noticias", "PERFIL", date(2026, 11, 21), exemplos)

    assert "## AVALIAÇÕES RECENTES DO USUÁRIO" in instrucoes
    gostou, nao_gostou = instrucoes.split("Não gostou (quer menos assim):")
    assert "- Rust 2.0 (nota que você deu: 6)" in gostou
    assert "- Cupom de desconto\n" in nao_gostou
    assert instrucoes.index("PERFIL") < instrucoes.index("AVALIAÇÕES")


def test_sem_exemplos_prompt_nao_muda() -> None:
    sem = cliente.montar_instrucoes("noticias", "PERFIL", date(2026, 11, 21))
    assert "AVALIAÇÕES" not in sem
    assert cliente.secao_exemplos([]) == ""


# ------------------------------------------------------------------ triagem


def _capturar(monkeypatch: pytest.MonkeyPatch) -> list[Sequence[Exemplo]]:
    recebidos: list[Sequence[Exemplo]] = []

    def falso(
        itens: Sequence[ItemPendente], modulo: Modulo, *, exemplos: Sequence[Exemplo] = ()
    ) -> list[Resultado]:
        recebidos.append(exemplos)
        return [Resultado(id=i.id, nota=5, resumo="r", tags=["ia"]) for i in itens]

    monkeypatch.setattr(cliente, "classificar_lote", falso)
    return recebidos


def test_triagem_manda_os_votos_ao_modelo(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    [antigo] = _semear(supabase, "noticias", ["Já votado"])
    supabase.tabelas["itens"][0]["status"] = "processado"
    _votar(supabase, antigo, 1, dias_atras=0)
    supabase.tabelas["feedback"][0]["criado_em"] = datetime.now(UTC).isoformat()
    banco.salvar_itens([Item(modulo="noticias", fonte="f", titulo="Novo", url="https://e.com/n")])
    recebidos = _capturar(monkeypatch)

    triagem.triar("noticias", pausa=0)

    assert [[e.titulo for e in lote] for lote in recebidos] == [["Já votado"]]


def test_falha_ao_ler_votos_nao_para_a_triagem(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(supabase, "noticias", ["Novo"])
    recebidos = _capturar(monkeypatch)

    def quebrado(*_a: Any, **_k: Any) -> list[Exemplo]:
        raise banco.ErroBanco("feedback fora do ar")

    monkeypatch.setattr(banco, "exemplos_feedback", quebrado)

    resumo = triagem.triar("noticias", pausa=0)

    assert recebidos == [[]]
    assert resumo.processados == 1


# ------------------------------------------------------------------ e-mail


def _item(id_: int, titulo: str = "Notícia") -> ItemResumo:
    return ItemResumo(
        id=id_, modulo="noticias", fonte="f", titulo=titulo, url=f"https://e.com/{id_}", nota=8
    )


def test_email_com_links_de_voto() -> None:
    mensagem = correio.montar_mensagem(
        [_item(42)], date(2026, 11, 21), nota_minima=6, portal_url="https://portal.exemplo/"
    )

    assert "https://portal.exemplo/votar?item=42&voto=1" in mensagem.texto
    assert "https://portal.exemplo/votar?item=42&voto=-1" in mensagem.texto
    assert 'href="https://portal.exemplo/votar?item=42&amp;voto=1"' in mensagem.html
    assert "👎 Menos assim" in mensagem.html


def test_email_sem_portal_nao_tem_links_de_voto() -> None:
    mensagem = correio.montar_mensagem([_item(42)], date(2026, 11, 21), nota_minima=6)
    assert "votar" not in mensagem.texto
    assert "votar" not in mensagem.html


def test_email_nao_repete_a_ultima_secao() -> None:
    """Regressão: a última seção (notícias) aparecia de novo, sem título, no fim do HTML."""
    mensagem = correio.montar_mensagem(
        [_item(1, "TITULO-UNICO")], date(2026, 11, 21), nota_minima=6
    )
    assert mensagem.html.count("TITULO-UNICO") == 1


# ------------------------------------------------------------------ configuração


def test_portal_url_valida(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTAL_URL", "https://mordenews.vercel.app/")
    assert config.ler_ambiente().portal_url == "https://mordenews.vercel.app"
    monkeypatch.setenv("PORTAL_URL", "mordenews.vercel.app")
    with pytest.raises(config.ErroConfiguracao):
        config.ler_ambiente()
