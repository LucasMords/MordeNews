from datetime import UTC, datetime

import httpx
import pytest

from radar import banco
from radar.coletores.html import ColetorIEL, ErroIEL, ler_sitemap, ler_vaga
from radar.coletores.registro import montar_coletores
from radar.modelos import Fonte, gerar_id_unico
from tests.conftest import AGORA, SiteFalso, cliente_http, fonte, ler_fixture

BASE = "https://carreiras.iel.org.br"
VAGA_WEB = f"{BASE}/TO/vaga/estagio/40001/estagio-em-desenvolvimento-web"
VAGA_SUPORTE = f"{BASE}/TO/vaga/estagio/40002/estagio-em-suporte-de-ti"


def _fonte() -> Fonte:
    return fonte(modulo="estagios", nome="iel-tocantins", tipo="iel", url=f"{BASE}/TO")


def _site() -> SiteFalso:
    pagina = httpx.Response(200, content=ler_fixture("iel_vaga.html"))
    return SiteFalso(
        {
            f"{BASE}/sitemap.xml": httpx.Response(200, content=ler_fixture("iel_sitemap.xml")),
            VAGA_WEB: pagina,
            VAGA_SUPORTE: pagina,
        }
    )


def _coletor(site: SiteFalso, conhecidas: frozenset[str] = frozenset()) -> ColetorIEL:
    return ColetorIEL(
        _fonte(),
        cliente_http(site),
        agora=lambda: AGORA,
        conhecido=lambda id_unico: id_unico in conhecidas,
    )


def test_sitemap_filtra_pelo_estado() -> None:
    entradas = ler_sitemap(ler_fixture("iel_sitemap.xml"), "/TO/vaga/")
    assert [e.url for e in entradas] == [
        VAGA_WEB,
        VAGA_SUPORTE,
        f"{BASE}/TO/vaga/estagio/30000/estagio-antigo",
    ]
    assert entradas[0].alterado_em == datetime(2026, 11, 18, 10, 0, tzinfo=UTC)


def test_sitemap_quebrado_e_erro() -> None:
    with pytest.raises(ErroIEL):
        ler_sitemap(b"<html>nao e xml", "/TO/vaga/")


def test_ler_vaga_extrai_campos_rotulados() -> None:
    titulo, texto = ler_vaga(ler_fixture("iel_vaga.html").decode("utf-8"))
    assert titulo == "Estágio em Desenvolvimento Web"
    linhas = texto.splitlines()
    assert linhas[0] == "Cód: 40001"
    assert "Empresa: EMPRESA EXEMPLO LTDA - PALMAS - TO" in linhas
    assert "Cursos: SISTEMAS DE INFORMAÇÃO CIÊNCIA DA COMPUTAÇÃO" in linhas
    assert "Cidade: Palmas" in linhas
    assert "Remuneração: R$ 1.200,00" in linhas
    assert linhas[-1] == "Formato de trabalho: Híbrido"
    # rótulo vazio some; script, cabeçalho e rodapé não entram
    assert not any(linha.startswith("Benefícios") for linha in linhas)
    assert "não é texto" not in texto
    assert "Faça login" not in texto
    assert "Rua Fictícia" not in texto


def test_pagina_sem_campos_e_erro() -> None:
    with pytest.raises(ErroIEL):
        ler_vaga("<html><body><h1>Página inicial</h1><p>nada aqui</p></body></html>")


def test_buscar_baixa_so_vagas_novas_na_janela() -> None:
    site = _site()
    itens = _coletor(site, conhecidas={gerar_id_unico(VAGA_SUPORTE)}).buscar()
    assert [i.url for i in itens] == [VAGA_WEB]
    item = itens[0]
    assert item.modulo == "estagios"
    assert item.fonte == "iel-tocantins"
    assert item.publicado_em == datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
    assert "Cidade: Palmas" in item.texto
    # vaga conhecida, vaga antiga e vaga de outro estado não são baixadas
    urls = site.urls()
    assert VAGA_SUPORTE not in urls
    assert not any("30000" in u or "/ES/" in u for u in urls)


def test_pagina_com_falha_nao_derruba_as_outras() -> None:
    site = _site()
    site.rotas[VAGA_SUPORTE] = httpx.Response(500)
    itens = _coletor(site).buscar()
    assert [i.url for i in itens] == [VAGA_WEB]


def test_todas_as_paginas_falhando_e_erro() -> None:
    site = _site()
    site.rotas[VAGA_WEB] = httpx.Response(500)
    site.rotas[VAGA_SUPORTE] = httpx.Response(500)
    with pytest.raises(ErroIEL):
        _coletor(site).buscar()


def test_nada_novo_nao_e_erro() -> None:
    conhecidas = {gerar_id_unico(VAGA_WEB), gerar_id_unico(VAGA_SUPORTE)}
    assert _coletor(_site(), conhecidas=conhecidas).buscar() == []


def test_falha_do_banco_baixa_assim_mesmo() -> None:
    def quebrado(_: str) -> bool:
        raise banco.ErroBanco("fora do ar")

    coletor = ColetorIEL(_fonte(), cliente_http(_site()), agora=lambda: AGORA, conhecido=quebrado)
    assert len(coletor.buscar()) == 2


def test_registro_monta_coletor_iel() -> None:
    assert isinstance(montar_coletores([_fonte()], cliente_http(SiteFalso()))[0], ColetorIEL)
