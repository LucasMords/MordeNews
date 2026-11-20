import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from google.genai import errors

from radar import config
from radar.ia import cliente
from radar.modelos import ItemPendente

IDS = {1, 2, 3}


def _resposta(*itens: dict[str, Any]) -> str:
    return json.dumps(list(itens))


def _item_ia(id_: int, **extra: Any) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "id": id_,
        "nota": 7,
        "resumo": "Resumo em português.",
        "tags": ["ia"],
        "descartar": False,
        "prazo": None,
    }
    dados.update(extra)
    return dados


def _pendente(id_: int, texto: str | None = "texto") -> ItemPendente:
    return ItemPendente(
        id=id_,
        modulo="noticias",
        fonte="fonte-x",
        titulo=f"Título {id_}",
        url=f"https://exemplo.com/{id_}",
        texto=texto,
    )


# --------------------------------------------------------- interpretar_resposta


def test_resposta_valida() -> None:
    texto = _resposta(_item_ia(1), _item_ia(2, nota=2, descartar=True, prazo="2026-12-01"))
    resultados = cliente.interpretar_resposta(texto, IDS)
    assert [r.id for r in resultados] == [1, 2]
    assert resultados[1].descartar and resultados[1].status == "descartado"
    assert resultados[1].prazo == date(2026, 12, 1)
    assert resultados[0].status == "processado"
    assert resultados[0].campos == {}


@pytest.mark.parametrize(
    "texto", ["", None, "isto não é json", "{quebrado", '"só uma string"', "42"]
)
def test_resposta_quebrada_devolve_lista_vazia(texto: str | None) -> None:
    assert cliente.interpretar_resposta(texto, IDS) == []


def test_resposta_com_cerca_de_markdown() -> None:
    texto = f"```json\n{_resposta(_item_ia(1))}\n```"
    assert [r.id for r in cliente.interpretar_resposta(texto, IDS)] == [1]


def test_resposta_embrulhada_em_objeto() -> None:
    texto = json.dumps({"itens": [_item_ia(3)]})
    assert [r.id for r in cliente.interpretar_resposta(texto, IDS)] == [3]


@pytest.mark.parametrize(
    "invalido",
    [
        _item_ia(2, nota=11),
        _item_ia(2, nota=-1),
        _item_ia(2, resumo=""),
        _item_ia(2, prazo="30/11/2026"),
        {"id": 2, "nota": 5},  # sem resumo
        "não é objeto",
    ],
)
def test_item_invalido_e_ignorado_sem_afetar_os_outros(invalido: Any) -> None:
    texto = json.dumps([_item_ia(1), invalido, _item_ia(3)])
    assert [r.id for r in cliente.interpretar_resposta(texto, IDS)] == [1, 3]


def test_id_desconhecido_ou_repetido_e_ignorado() -> None:
    texto = _resposta(_item_ia(1, nota=9), _item_ia(1, nota=2), _item_ia(99))
    resultados = cliente.interpretar_resposta(texto, IDS)
    assert [(r.id, r.nota) for r in resultados] == [(1, 9)]


@pytest.mark.parametrize("prazo", [None, "null", "", "None"])
def test_prazo_vazio_vira_none(prazo: str | None) -> None:
    [resultado] = cliente.interpretar_resposta(_resposta(_item_ia(1, prazo=prazo)), IDS)
    assert resultado.prazo is None


def test_tags_normalizadas_e_filtradas_pelo_vocabulario() -> None:
    texto = _resposta(
        _item_ia(1, tags=[" IA ", "ia", "Java", "inventada"]),
        _item_ia(2, tags=["inventada"]),
    )
    resultados = cliente.interpretar_resposta(texto, IDS, cliente.TAGS_NOTICIAS)
    assert resultados[0].tags == ["ia", "java"]
    assert resultados[1].tags == ["outros"]


# ------------------------------------------------------------ montagem do prompt


def test_conteudo_so_tem_id_titulo_e_texto_truncado() -> None:
    conteudo = cliente.montar_conteudo([_pendente(1, "x" * 5000), _pendente(2, None)])
    lista = json.loads(conteudo.split("\n", 1)[1])
    assert lista[0] == {"id": 1, "titulo": "Título 1", "texto": "x" * cliente.LIMITE_TEXTO_IA}
    assert lista[1]["texto"] == cliente.SEM_TEXTO
    assert "exemplo.com" not in conteudo and "fonte-x" not in conteudo


@pytest.mark.parametrize("vazio", [None, "", "   \n "])
def test_texto_vazio_vira_aviso_explicito(vazio: str | None) -> None:
    assert cliente.texto_para_ia(vazio) == cliente.SEM_TEXTO


def test_metadados_do_hacker_news_viram_aviso_com_pontos() -> None:
    hn = (
        "Article URL: https://hy.tencent.ai/research/hy4-flash "
        "Comments URL: https://news.ycombinator.com/item?id=1 Points: 412 # Comments: 187"
    )
    texto = cliente.texto_para_ia(hn)
    assert texto.startswith(cliente.SEM_TEXTO)
    assert "Pontos no Hacker News: 412; comentários: 187" in texto
    assert "news.ycombinator.com" not in texto


def test_texto_normal_nao_e_alterado() -> None:
    assert cliente.texto_para_ia("  Article URL: no meio do texto normal.  ") == (
        "Article URL: no meio do texto normal."
    )


def test_instrucoes_incluem_prompt_perfil_e_data() -> None:
    instrucoes = cliente.montar_instrucoes("noticias", "PERFIL-DE-TESTE", date(2026, 11, 18))
    assert "filtro de notícias" in instrucoes
    assert "PERFIL-DE-TESTE" in instrucoes
    assert "2026-11-18" in instrucoes


def test_prompt_de_noticias_lista_todas_as_tags_do_vocabulario() -> None:
    prompt = cliente.carregar_prompt("noticias")
    faltando = [t for t in cliente.TAGS_NOTICIAS if f"`{t}`" not in prompt]
    assert faltando == []


def test_esquema_restringe_tags_e_exige_campos() -> None:
    esquema = cliente.esquema_resposta("noticias")
    item = esquema["items"]
    assert item["properties"]["tags"]["items"]["enum"] == list(cliente.TAGS_NOTICIAS)
    assert set(item["required"]) == {"id", "nota", "resumo", "tags", "descartar", "prazo"}


def test_modulo_sem_prompt_da_erro_claro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "noticias.md").write_text("prompt", encoding="utf-8")
    monkeypatch.setattr(cliente, "PASTA_PROMPTS", tmp_path)
    with pytest.raises(config.ErroConfiguracao, match="concursos"):
        cliente.carregar_prompt("concursos")
    assert cliente.modulos_com_prompt() == ["noticias"]


def test_todos_os_modulos_tem_prompt() -> None:
    assert cliente.modulos_com_prompt() == ["noticias", "estagios", "concursos"]


# ----------------------------------------------------------------- retentativas


def _erro(codigo: int) -> errors.APIError:
    corpo = {"error": {"code": codigo, "message": f"erro {codigo}", "status": "X"}}
    return errors.ClientError(codigo, corpo) if codigo < 500 else errors.ServerError(codigo, corpo)


class Sequencia:
    """Chamável que levanta as exceções dadas, em ordem, e depois devolve 'ok'."""

    def __init__(self, *falhas: Exception) -> None:
        self.falhas = list(falhas)
        self.chamadas = 0

    def __call__(self) -> str:
        self.chamadas += 1
        if self.falhas:
            raise self.falhas.pop(0)
        return "ok"


def test_429_com_backoff_e_depois_sucesso() -> None:
    esperas: list[float] = []
    chamar = Sequencia(_erro(429), _erro(429))
    assert cliente.com_retentativas(chamar, dormir=esperas.append) == "ok"
    assert esperas == [5.0, 15.0]


def test_429_persistente_vira_cota_esgotada() -> None:
    esperas: list[float] = []
    chamar = Sequencia(*[_erro(429)] * 4)
    with pytest.raises(cliente.CotaEsgotada):
        cliente.com_retentativas(chamar, dormir=esperas.append)
    assert esperas == [5.0, 15.0, 45.0]
    assert chamar.chamadas == 4


def test_5xx_persistente_vira_erro_ia_mas_nao_cota() -> None:
    with pytest.raises(cliente.ErroIA) as info:
        cliente.com_retentativas(Sequencia(*[_erro(503)] * 4), dormir=lambda _: None)
    assert not isinstance(info.value, cliente.CotaEsgotada)


def test_erro_400_nao_tem_retentativa() -> None:
    esperas: list[float] = []
    chamar = Sequencia(_erro(400))
    with pytest.raises(cliente.ErroIA, match="400"):
        cliente.com_retentativas(chamar, dormir=esperas.append)
    assert esperas == [] and chamar.chamadas == 1


def test_falha_de_rede_tem_retentativa() -> None:
    chamar = Sequencia(httpx.ConnectError("sem rede"))
    assert cliente.com_retentativas(chamar, dormir=lambda _: None) == "ok"


# ------------------------------------------------------------- classificar_lote


def test_classificar_lote_ponta_a_ponta(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[str, str]] = []

    def modelo_falso(instrucoes: str, conteudo: str, esquema: dict[str, Any]) -> str:
        chamadas.append((instrucoes, conteudo))
        return _resposta(_item_ia(1, nota=9), _item_ia(2, nota=3))

    monkeypatch.setattr(config, "carregar_perfil", lambda: "PERFIL-X")
    monkeypatch.setattr(cliente, "_chamar_modelo", modelo_falso)

    resultados = cliente.classificar_lote([_pendente(1), _pendente(2)], "noticias")

    assert [(r.id, r.nota) for r in resultados] == [(1, 9), (2, 3)]
    assert len(chamadas) == 1  # um lote = uma chamada
    assert "PERFIL-X" in chamadas[0][0]


def test_classificar_lote_vazio_nao_chama_o_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    def proibido(*_: Any) -> str:
        raise AssertionError("não deveria chamar o modelo")

    monkeypatch.setattr(cliente, "_chamar_modelo", proibido)
    assert cliente.classificar_lote([], "noticias") == []


# --------------------------------------------------------------------- estágios

CAMPOS_VAGA: dict[str, Any] = {
    "empresa": "Empresa Exemplo",
    "area": "Desenvolvimento back-end",
    "cidade": "Palmas - TO",
    "remoto": False,
    "bolsa": "R$ 1.200,00",
    "requisitos": ["Cursando SI", "Git"],
    "link_inscricao": None,
}


def _vaga(id_: int, texto: str = "texto da vaga") -> ItemPendente:
    return ItemPendente(
        id=id_,
        modulo="estagios",
        fonte="iel-tocantins",
        titulo=f"Estágio {id_}",
        url=f"https://vagas.exemplo.com/{id_}",
        texto=texto,
    )


def test_campos_de_vaga_validados_e_normalizados() -> None:
    campos = {**CAMPOS_VAGA, "bolsa": "", "cidade": "null", "requisitos": None, "extra": "x"}
    texto = _resposta(_item_ia(1, tags=["estagio"], campos=campos))
    [resultado] = cliente.interpretar_resposta(
        texto, IDS, cliente.TAGS_ESTAGIOS, cliente.CamposEstagio
    )
    assert resultado.campos["empresa"] == "Empresa Exemplo"
    assert resultado.campos["bolsa"] is None
    assert resultado.campos["cidade"] is None
    assert resultado.campos["requisitos"] == []
    assert "extra" not in resultado.campos


def test_vaga_com_campos_invalidos_fica_pendente() -> None:
    texto = _resposta(
        _item_ia(1, campos={**CAMPOS_VAGA, "remoto": "talvez"}),
        _item_ia(2, campos=CAMPOS_VAGA),
    )
    resultados = cliente.interpretar_resposta(texto, IDS, None, cliente.CamposEstagio)
    assert [r.id for r in resultados] == [2]


def test_link_que_nao_esta_no_texto_e_descartado() -> None:
    itens = [_vaga(1, "Inscreva-se em https://empresa.com/vaga/1"), _vaga(2), _vaga(3)]
    resultados = [
        cliente.Resultado(id=1, nota=8, resumo="r", campos={"link_inscricao": "https://empresa.com/vaga/1"}),
        cliente.Resultado(id=2, nota=8, resumo="r", campos={"link_inscricao": "https://inventado.com"}),
        cliente.Resultado(id=3, nota=8, resumo="r", campos={"link_inscricao": "https://vagas.exemplo.com/3"}),
    ]  # fmt: skip
    conferidos = cliente.conferir_links(resultados, itens)
    assert [r.campos["link_inscricao"] for r in conferidos] == [
        "https://empresa.com/vaga/1",
        None,  # inventado
        "https://vagas.exemplo.com/3",  # a própria URL da vaga
    ]


def test_esquema_de_estagios_exige_campos_e_usa_vocabulario_proprio() -> None:
    item = cliente.esquema_resposta("estagios")["items"]
    assert "campos" in item["required"]
    assert item["properties"]["tags"]["items"]["enum"] == list(cliente.TAGS_ESTAGIOS)
    assert set(item["properties"]["campos"]["required"]) == {
        "empresa", "area", "cidade", "remoto", "bolsa", "requisitos", "link_inscricao"
    }  # fmt: skip
    assert "campos" not in cliente.esquema_resposta("noticias")["items"]["properties"]


def test_prompt_de_estagios_lista_todas_as_tags_do_vocabulario() -> None:
    prompt = cliente.carregar_prompt("estagios")
    for tag in cliente.TAGS_ESTAGIOS:
        assert f"`{tag}`" in prompt


def test_conteudo_de_estagios_pede_vagas() -> None:
    assert cliente.montar_conteudo([_vaga(1)], "estagios").startswith("Avalie estas vagas:")


def test_classificar_lote_de_estagios(monkeypatch: pytest.MonkeyPatch) -> None:
    def modelo_falso(instrucoes: str, conteudo: str, esquema: dict[str, Any]) -> str:
        assert "estágio em tecnologia" in instrucoes
        campos = {**CAMPOS_VAGA, "link_inscricao": "https://inventado.com"}
        return _resposta(_item_ia(1, nota=9, tags=["estagio", "tocantins"], campos=campos))

    monkeypatch.setattr(config, "carregar_perfil", lambda: "PERFIL-X")
    monkeypatch.setattr(cliente, "_chamar_modelo", modelo_falso)
    [resultado] = cliente.classificar_lote([_vaga(1)], "estagios")
    assert resultado.tags == ["estagio", "tocantins"]
    assert resultado.campos["empresa"] == "Empresa Exemplo"
    assert resultado.campos["link_inscricao"] is None
