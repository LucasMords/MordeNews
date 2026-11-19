from datetime import UTC, datetime
from typing import Any

from radar.entrega.agrupamento import agrupar, cves, nomes, palavras
from radar.modelos import ItemResumo


def _item(id_: int, titulo: str, nota: int = 7, **extra: Any) -> ItemResumo:
    dados: dict[str, Any] = {
        "id": id_,
        "modulo": "noticias",
        "fonte": f"fonte-{id_}",
        "titulo": titulo,
        "url": f"https://e.com/{id_}",
        "nota": nota,
        "publicado_em": datetime(2026, 11, 18, id_ % 24, tzinfo=UTC),
    }
    dados.update(extra)
    return ItemResumo.model_validate(dados)


def test_palavras_ignora_acento_caixa_e_palavras_vazias() -> None:
    assert palavras("Falha crítica no OpenJDK: a correção") == {
        "falha",
        "critica",
        "openjdk",
        "correcao",
    }


def test_cves_no_titulo_e_no_resumo() -> None:
    item = _item(1, "Java4Shell (cve-2026-114938)", resumo="Veja também CVE-2026-5555.")
    assert cves(item) == {"CVE-2026-114938", "CVE-2026-5555"}


def test_mesmo_cve_agrupa_mesmo_com_titulos_diferentes() -> None:
    itens = [
        _item(
            1, "Java4Shell: filtro falha ao localizar Corretto", nota=9, resumo="CVE-2026-114938"
        ),
        _item(2, "Oracle corrige 11 falhas no Java SE", nota=10, resumo="Inclui CVE-2026-114938."),
        _item(3, "Nvidia para de vender chips para a China", nota=7),
    ]
    assuntos = agrupar(itens)
    assert [(a.principal.id, [r.id for r in a.repetidos]) for a in assuntos] == [
        (2, [1]),  # o de maior nota é o principal
        (3, []),
    ]


def test_titulos_parecidos_agrupam() -> None:
    itens = [
        _item(1, "Quad9 Is Leaving France: Why DNS Resolvers Are the Wrong Place"),
        _item(2, "Quad9 is leaving France"),
        _item(3, "Quad9's withdrawal from France: a canary in the coal mine"),
    ]
    [assunto] = agrupar(itens)  # o 3 entra pela semelhança com o 2 (transitividade)
    assert sorted(i.id for i in assunto.itens) == [1, 2, 3]


def test_cves_diferentes_nunca_agrupam_mesmo_com_titulos_parecidos() -> None:
    itens = [
        _item(
            1, "Falha crítica Java4Shell permite execução remota de código", resumo="CVE-2026-1111"
        ),
        _item(
            2,
            "Falha crítica no Apache Roller permite execução remota de código",
            resumo="CVE-2026-2222",
        ),
    ]
    assert len(agrupar(itens)) == 2


def test_titulo_parecido_sem_cve_agrupa_com_item_que_tem_cve() -> None:
    itens = [
        _item(1, "Java4Shell falha crítica no OpenJDK", resumo="CVE-2026-114938"),
        _item(2, "Java4Shell: falha crítica no OpenJDK permite RCE"),
    ]
    assert len(agrupar(itens)) == 1


def test_nome_com_letras_e_numeros_agrupa() -> None:
    itens = [
        _item(1, "Java4Shell: RCE in OpenJDK when processing Base64"),
        _item(2, "Oracle publica 655 patches e corrige falha Java4Shell"),
        _item(3, "Ruby2Shell: pre-auth RCE on Rails"),
    ]
    assert nomes("Java4Shell: RCE in OpenJDK") == {"java4shell"}
    assert nomes("Release 2026 do Java 27") == set()  # só número ou só letra não conta
    grupos = sorted(sorted(i.id for i in a.itens) for a in agrupar(itens))
    assert grupos == [[1, 2], [3]]


def test_uma_palavra_em_comum_nao_basta() -> None:
    itens = [
        _item(1, "Nvidia isn't selling any more AI chips"),
        _item(2, "Nvidia afirma que não pretende reconduzir Jensen Huang"),
    ]
    assert len(agrupar(itens)) == 2


def test_agrupamento_e_transitivo() -> None:
    itens = [
        _item(1, "A", resumo="CVE-2026-0001"),
        _item(2, "B", resumo="CVE-2026-0001 e CVE-2026-0002"),
        _item(3, "C", resumo="CVE-2026-0002"),
    ]
    [assunto] = agrupar(itens)
    assert sorted(i.id for i in assunto.itens) == [1, 2, 3]


def test_modulos_diferentes_nunca_agrupam() -> None:
    itens = [
        _item(1, "Concurso IFTO 2026 abre inscrições", modulo="concursos"),
        _item(2, "Concurso IFTO 2026 abre inscrições", modulo="noticias"),
    ]
    assert len(agrupar(itens)) == 2


def test_assuntos_saem_ordenados_por_nota() -> None:
    itens = [_item(1, "Um assunto", nota=6), _item(2, "Outro tema", nota=9)]
    assert [a.nota for a in agrupar(itens)] == [9, 6]
