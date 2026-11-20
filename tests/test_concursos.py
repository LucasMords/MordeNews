"""Bloco 5: coletores de concursos (PCI e feed + página), campos e agrupamento."""

from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from radar.coletores.html import ColetorPCI, ErroPCI, ler_pci
from radar.coletores.registro import montar_coletores
from radar.coletores.rss import ColetorRSSPagina, ler_artigo
from radar.entrega.agrupamento import agrupar
from radar.ia import cliente
from radar.modelos import CamposConcurso, Fonte, ItemPendente, ItemResumo, gerar_id_unico
from tests.conftest import AGORA, SiteFalso, cliente_http, fonte, ler_fixture

PCI = "https://www.pciconcursos.com.br/concursos/"
FEED = "https://concursosnobrasil.com/concursos/to/feed/"
ARTIGO = "https://concursosnobrasil.com/concursos/to/2026/11/16/concurso-camara-de-paraiso-exemplo/"


def _fonte_pci(**extra: Any) -> Fonte:
    dados = {"modulo": "concursos", "nome": "pci-to-go", "tipo": "pci", "url": PCI}
    return fonte(**{**dados, "ufs": ["to", "GO"], **extra})


def _fonte_cnb() -> Fonte:
    return fonte(
        modulo="concursos", nome="cnb-tocantins", tipo="rss-pagina", url=FEED, janela_horas=336
    )


# ------------------------------------------------------------------------------ PCI


def test_pci_filtra_ufs_e_monta_texto_com_os_campos() -> None:
    concursos = ler_pci(ler_fixture("pci_concursos.html").decode("utf-8"), ["TO", "GO"])

    assert [titulo for titulo, _, _ in concursos] == [
        "Prefeitura de Exemplópolis - GO abre concurso público com salários de até R$ 4.508,28",
        "Câmara de Exemplópolis - GO abre concurso público",
        "Câmara de Paraíso Exemplo",  # sem `title` no link: usa o nome do órgão
    ]
    _, url, texto = concursos[0]
    assert url.endswith("/prefeitura-de-exemplopolis-go-abre-concurso")
    assert texto.splitlines() == [
        "Órgão: Prefeitura de Exemplópolis",
        "UF: GO",
        "Vagas e salário: 2956 vagas até R$ 4.508,28",
        "Cargos: Vários Cargos",
        "Escolaridade: Médio / Técnico / Superior",
        "Inscrições até: 09/12/2026",
    ]
    assert concursos[1][2].endswith("Inscrições até: 13/12/2026 a 13/01/2027")


def test_pci_layout_desconhecido_e_erro() -> None:
    with pytest.raises(ErroPCI):
        ler_pci("<html><body><p>nada</p></body></html>", ["TO"])


def test_coletor_pci_faz_uma_requisicao_e_devolve_itens() -> None:
    site = SiteFalso({PCI: httpx.Response(200, content=ler_fixture("pci_concursos.html"))})
    coletor = ColetorPCI(_fonte_pci(), cliente_http(site), agora=lambda: AGORA)

    itens = coletor.buscar()

    assert [p for p in site.urls() if not p.endswith("robots.txt")] == [PCI]
    assert len(itens) == 3
    assert {i.modulo for i in itens} == {"concursos"}
    assert all(i.publicado_em is None for i in itens)


def test_coletor_pci_sem_ufs_e_erro() -> None:
    coletor = ColetorPCI(_fonte_pci(ufs=[]), cliente_http(SiteFalso()))
    with pytest.raises(ErroPCI, match="ufs"):
        coletor.buscar()


def test_registro_monta_os_tipos_novos() -> None:
    coletores = montar_coletores([_fonte_pci(), _fonte_cnb()], cliente_http(SiteFalso()))
    assert [type(c) for c in coletores] == [ColetorPCI, ColetorRSSPagina]


# ---------------------------------------------------------------- feed + página


def test_ler_artigo_poe_dados_importantes_primeiro_e_tira_ruido() -> None:
    texto = ler_artigo(ler_fixture("cnb_artigo.html").decode("utf-8"), ARTIGO)
    linhas = texto.splitlines()

    assert linhas[0] == "Link do edital: https://banca.exemplo.com/edital-001-2026.pdf"
    assert "14 vagas imediatas" in linhas[1]  # link no meio da frase não quebra o parágrafo
    assert any("18 de dezembro de 2026" in linha for linha in linhas[:8])
    assert "Auxiliar de Serviços Gerais : exige nível fundamental;" in linhas
    for ruido in ("continua depois", "Seguir no Google", "Concurso Outro", "Propaganda", "var x"):
        assert ruido not in texto


def _site_cnb(artigo: httpx.Response | Exception | None = None) -> SiteFalso:
    pagina = artigo or httpx.Response(200, content=ler_fixture("cnb_artigo.html"))
    return SiteFalso(
        {FEED: httpx.Response(200, content=ler_fixture("cnb_feed.xml")), ARTIGO: pagina}
    )


def test_rss_pagina_abre_o_artigo_dos_itens_novos() -> None:
    site = _site_cnb()
    coletor = ColetorRSSPagina(
        _fonte_cnb(), cliente_http(site), agora=lambda: AGORA, conhecido=lambda _: False
    )

    itens = coletor.buscar()

    assert [i.url for i in itens] == [ARTIGO]  # o de outubro ficou fora da janela de 14 dias
    assert itens[0].texto.startswith("Concurso Câmara de Paraíso Exemplo foi anunciado")
    assert "18 de dezembro de 2026" in itens[0].texto
    assert itens[0].id_unico == gerar_id_unico(ARTIGO)


def test_rss_pagina_nao_baixa_de_novo_o_que_ja_esta_no_banco() -> None:
    site = _site_cnb()
    coletor = ColetorRSSPagina(
        _fonte_cnb(), cliente_http(site), agora=lambda: AGORA, conhecido=lambda _: True
    )
    coletor.buscar()
    assert ARTIGO not in site.urls()


def test_rss_pagina_sem_artigo_fica_com_o_trecho_do_feed() -> None:
    site = _site_cnb(httpx.Response(500))
    coletor = ColetorRSSPagina(
        _fonte_cnb(), cliente_http(site), agora=lambda: AGORA, conhecido=lambda _: False
    )
    itens = coletor.buscar()
    assert (
        itens[0].texto
        == "Concurso Câmara de Paraíso Exemplo foi anunciado com vagas de vários níveis."
    )


# ----------------------------------------------------------------- campos da IA


def test_campos_concurso_normaliza_e_descarta_o_invalido() -> None:
    campos = CamposConcurso.model_validate(
        {
            "orgao": " IFG ",
            "cargos": None,
            "escolaridade": "null",
            "salario_max": "R$ 5.215,39",
            "vagas": "36 vagas",
            "data_prova": "17/01/2027",  # fora do ISO: vira nulo, sem derrubar o item
            "link_edital": "edital.pdf",
            "extra": "ignorado",
        }
    )
    assert campos.model_dump(mode="json") == {
        "orgao": "IFG",
        "cargos": [],
        "escolaridade": None,
        "salario_max": "R$ 5.215,39",
        "vagas": 36,
        "data_prova": None,
        "link_edital": None,
    }


def test_interpretar_resposta_de_concursos_valida_campos_e_tags() -> None:
    resposta = """[{"id": 7, "nota": 5, "resumo": "Câmara abre 14 vagas.",
      "tags": ["tocantins", "xyz"], "descartar": false, "prazo": "2026-12-18",
      "campos": {"orgao": "Câmara de Paraíso Exemplo", "cargos": ["Vigia"], "escolaridade": null,
                 "salario_max": "R$ 6.244,07", "vagas": 14, "data_prova": "2027-01-17",
                 "link_edital": null}}]"""
    (resultado,) = cliente.interpretar_resposta(
        resposta, {7}, cliente.TAGS_CONCURSOS, cliente.CAMPOS_POR_MODULO["concursos"]
    )
    assert resultado.prazo == date(2026, 12, 18)
    assert resultado.tags == ["tocantins"]
    assert resultado.campos["data_prova"] == "2027-01-17"  # JSON, pronto para o banco
    assert resultado.campos["vagas"] == 14


def test_link_do_edital_fora_do_texto_e_descartado() -> None:
    item = ItemPendente(
        id=1, modulo="concursos", fonte="f", titulo="t", url="https://e.com/1",
        texto="Link do edital: https://banca.exemplo.com/edital.pdf",
    )  # fmt: skip
    bom = cliente.Resultado(
        id=1, nota=5, resumo="r", campos={"link_edital": "https://banca.exemplo.com/edital.pdf"}
    )
    inventado = cliente.Resultado(
        id=1, nota=5, resumo="r", campos={"link_edital": "https://inventado.com/edital.pdf"}
    )
    assert cliente.conferir_links([bom], [item])[0].campos["link_edital"]
    assert cliente.conferir_links([inventado], [item])[0].campos["link_edital"] is None


def test_esquema_de_concursos_pede_os_campos_da_secao_4() -> None:
    esquema = cliente.esquema_resposta("concursos")
    campos = esquema["items"]["properties"]["campos"]
    assert set(campos["required"]) == {
        "orgao", "cargos", "escolaridade", "salario_max", "vagas", "data_prova", "link_edital"
    }  # fmt: skip


# -------------------------------------------------------------------- agrupamento


def _concurso(id_: int, fonte_: str, orgao: str) -> ItemResumo:
    return ItemResumo(
        id=id_, modulo="concursos", fonte=fonte_, titulo=f"Concurso {orgao}",
        url=f"https://e.com/{id_}", nota=5, campos={"orgao": orgao},
        publicado_em=datetime(2026, 11, 18, tzinfo=UTC),
    )  # fmt: skip


def test_mesmo_concurso_em_duas_fontes_e_agrupado() -> None:
    a = _concurso(1, "pci-to-go", "Prefeitura de Aparecida de Goiânia")
    b = _concurso(2, "cnb-goias", "Prefeitura Municipal de Aparecida de Goiânia")
    assert len(agrupar([a, b])) == 1


def test_prefeitura_e_camara_da_mesma_cidade_nao_agrupam() -> None:
    a = _concurso(1, "pci-to-go", "Prefeitura de Campo Limpo de Goiás")
    b = _concurso(2, "cnb-goias", "Câmara de Campo Limpo de Goiás")
    assert len(agrupar([a, b])) == 2


def test_concursos_da_mesma_fonte_nao_agrupam() -> None:
    a = _concurso(1, "pci-to-go", "IFG")
    b = _concurso(2, "pci-to-go", "IFG")
    assert len(agrupar([a, b])) == 2


def test_link_para_outro_artigo_do_site_nao_e_edital() -> None:
    texto = ler_artigo(ler_fixture("cnb_artigo.html").decode("utf-8"), ARTIGO)
    assert "concurso-ibge" not in texto
    assert texto.count("Link do edital:") == 1


def test_mesmo_orgao_escrito_em_outra_ordem_agrupa() -> None:
    a = _concurso(
        1, "pci-to-go", "IFG - Instituto Federal de Educação, Ciência e Tecnologia de Goiás"
    )
    b = _concurso(
        2, "cnb-goias", "Instituto Federal de Educação, Ciência e Tecnologia de Goiás (IFG)"
    )
    assert len(agrupar([a, b])) == 1


def test_selecoes_diferentes_do_mesmo_orgao_nao_agrupam() -> None:
    estagio = _concurso(1, "cnb-goias", "Saneago").model_copy(update={"prazo": date(2026, 11, 29)})
    aprendiz = _concurso(2, "pci-to-go", "Saneago").model_copy(update={"prazo": date(2026, 11, 24)})
    sem_prazo = _concurso(3, "cnb-tocantins", "Saneago")
    assert len(agrupar([estagio, aprendiz])) == 2
    assert len(agrupar([estagio, sem_prazo])) == 1


def test_orgaos_que_so_tem_palavras_genericas_em_comum_nao_agrupam() -> None:
    faina = _concurso(1, "pci-to-go", "Prefeitura e Câmara de Faina")
    campo_limpo = _concurso(2, "cnb-goias", "Prefeitura e Câmara Municipal de Campo Limpo de Goiás")
    campo_limpo_pci = _concurso(
        3, "pci-to-go", "Prefeitura de Campo Limpo de Goiás e Câmara de Campo Limpo de Goiás"
    )
    assuntos = agrupar([faina, campo_limpo, campo_limpo_pci])
    assert sorted(len(a.itens) for a in assuntos) == [1, 2]
