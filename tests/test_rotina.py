"""Bloco 8: ferramenta das rotinas do Claude (scripts/rotina.py), sem rede."""

import hashlib
import importlib.util
import io
import json
import sys
import urllib.error
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

_CAMINHO = Path(__file__).parents[1] / "scripts" / "rotina.py"
_spec = importlib.util.spec_from_file_location("rotina", _CAMINHO)
assert _spec and _spec.loader
rotina = importlib.util.module_from_spec(_spec)
sys.modules["rotina"] = rotina
_spec.loader.exec_module(rotina)


class RespostaFalsa(io.BytesIO):
    def __enter__(self) -> "RespostaFalsa":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co/")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    monkeypatch.setenv("ROTINA_TOKEN", "t" * 43)


@pytest.fixture
def pedidos(monkeypatch: pytest.MonkeyPatch, env: None) -> list[Any]:
    """Captura as requisições e responde com `pedidos.resposta`."""
    capturados: list[Any] = []

    def urlopen(pedido: Any, timeout: float) -> RespostaFalsa:
        capturados.append(pedido)
        return RespostaFalsa(json.dumps(urlopen.resposta).encode())  # type: ignore[attr-defined]

    urlopen.resposta = []  # type: ignore[attr-defined]
    monkeypatch.setattr(rotina.urllib.request, "urlopen", urlopen)
    capturados.append(urlopen)  # o primeiro elemento guarda a função, para ajustar a resposta
    return capturados


def test_token_e_hash_batem_com_o_sql() -> None:
    token, hash_ = rotina.gerar_token()
    assert len(token) >= 32  # a função do banco exige 32..200 caracteres
    assert hash_ == hashlib.sha256(token.encode()).hexdigest()


def test_ambiente_incompleto(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "ROTINA_TOKEN"):
        monkeypatch.delenv(nome, raising=False)
    with pytest.raises(rotina.ErroRotina, match="ROTINA_TOKEN"):
        rotina.ambiente()


def test_ler_manda_token_e_desde_e_compacta(pedidos: list[Any]) -> None:
    pedidos[0].resposta = [{"id": 1, "titulo": "A", "resumo": None, "tags": [], "nota": 8}]

    itens = rotina.ler(24, agora=datetime(2026, 11, 21, 12, tzinfo=UTC))

    pedido = pedidos[1]
    assert pedido.full_url == "https://abc.supabase.co/rest/v1/rpc/rotina_itens"
    assert pedido.headers["Apikey"] == "sb_publishable_x"
    assert "Authorization" not in pedido.headers  # chave publishable não é JWT
    assert json.loads(pedido.data) == {"token": "t" * 43, "desde": "2026-11-20T12:00:00+00:00"}
    assert itens == [{"id": 1, "titulo": "A", "nota": 8}]


def test_publicar(pedidos: list[Any]) -> None:
    pedidos[0].resposta = 7

    novo = rotina.publicar("diaria", " Edição ", "## Oi\n", date(2026, 11, 21))

    assert novo == 7
    assert json.loads(pedidos[1].data) == {
        "token": "t" * 43,
        "tipo": "diaria",
        "referencia": "2026-11-21",
        "titulo": "Edição",
        "conteudo": "## Oi",
    }


@pytest.mark.parametrize(
    ("tipo", "titulo", "conteudo"),
    [
        ("mensal", "T", "c"),
        ("diaria", "  ", "c"),
        ("diaria", "T", ""),
        ("diaria", "T", "x" * 20_001),
    ],
)
def test_publicar_recusa_edicao_invalida(tipo: str, titulo: str, conteudo: str) -> None:
    with pytest.raises(rotina.ErroRotina):
        rotina.validar_edicao(tipo, titulo, conteudo)


def test_erro_http_vira_mensagem(monkeypatch: pytest.MonkeyPatch, env: None) -> None:
    def urlopen(pedido: Any, timeout: float) -> None:
        raise urllib.error.HTTPError(
            pedido.full_url,
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"message":"token da rotina inv\xc3\xa1lido"}'),
        )

    monkeypatch.setattr(rotina.urllib.request, "urlopen", urlopen)
    with pytest.raises(rotina.ErroRotina, match=r"403.*token da rotina inválido"):
        rotina.ler(30)


def test_hoje_em_brasilia() -> None:
    # 01:00 UTC ainda é o dia anterior em Brasília
    assert rotina.hoje_brasilia(datetime(2026, 11, 22, 1, tzinfo=UTC)) == date(2026, 11, 21)


def test_cli_publicar(
    pedidos: list[Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pedidos[0].resposta = 3
    arquivo = tmp_path / "edicao.md"
    arquivo.write_text("## Destaques\n- item", encoding="utf-8")

    codigo = rotina.main(
        ["publicar", "semanal", str(arquivo), "--titulo", "Semana", "--referencia", "2026-11-22"]
    )

    assert codigo == 0
    assert "edição semanal de 2026-11-22 publicada (id 3)" in capsys.readouterr().out
