from pathlib import Path

import pytest

from radar import config


def _limpar_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "NOTA_MINIMA_RESUMO",
        "RADAR_CONTATO",
    ):
        monkeypatch.delenv(nome, raising=False)


def test_valores_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    _limpar_ambiente(monkeypatch)
    cfg = config.ler_ambiente()
    assert cfg.nota_minima_resumo == 6
    assert cfg.gemini_model == "gemini-2.5-flash-lite"
    assert cfg.supabase_url is None


def test_exigir_supabase_sem_variaveis(monkeypatch: pytest.MonkeyPatch) -> None:
    _limpar_ambiente(monkeypatch)
    with pytest.raises(config.ErroConfiguracao, match="SUPABASE_URL"):
        config.ler_ambiente().exigir_supabase()


def test_exigir_supabase_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _limpar_ambiente(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sb_secret_xyz")
    assert config.ler_ambiente().exigir_supabase() == ("https://abc.supabase.co", "sb_secret_xyz")


def test_repr_nao_expoe_segredos(monkeypatch: pytest.MonkeyPatch) -> None:
    _limpar_ambiente(monkeypatch)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "segredo-super-secreto")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-secreto")
    texto = repr(config.ler_ambiente())
    assert "segredo-super-secreto" not in texto
    assert "token-secreto" not in texto


def test_nota_minima_invalida(monkeypatch: pytest.MonkeyPatch) -> None:
    _limpar_ambiente(monkeypatch)
    monkeypatch.setenv("NOTA_MINIMA_RESUMO", "seis")
    with pytest.raises(config.ErroConfiguracao, match="NOTA_MINIMA_RESUMO"):
        config.ler_ambiente()


def test_carregar_fontes(tmp_path: Path) -> None:
    arquivo = tmp_path / "fontes.yaml"
    arquivo.write_text(
        "noticias:\n  - nome: exemplo\n    tipo: rss\n    url: https://e.com/feed\nestagios:\n",
        encoding="utf-8",
    )
    fontes = config.carregar_fontes(arquivo)
    assert fontes["noticias"][0]["nome"] == "exemplo"
    assert fontes["estagios"] == []


def test_carregar_fontes_formato_invalido(tmp_path: Path) -> None:
    arquivo = tmp_path / "fontes.yaml"
    arquivo.write_text("noticias: nao-e-lista\n", encoding="utf-8")
    with pytest.raises(config.ErroConfiguracao):
        config.carregar_fontes(arquivo)


def test_fontes_yaml_do_repositorio_e_valido() -> None:
    assert set(config.carregar_fontes()) >= {"noticias", "estagios", "concursos"}
    fontes = config.carregar_fontes_validas()
    noticias = [f for f in fontes if f.modulo == "noticias"]
    assert len(noticias) == 10
    assert all(f.tipo == "rss" and f.janela_horas == 72 and f.limite == 50 for f in noticias)


def _yaml(tmp_path: Path, conteudo: str) -> Path:
    arquivo = tmp_path / "fontes.yaml"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


@pytest.mark.parametrize(
    ("conteudo", "trecho_do_erro"),
    [
        ("noticias:\n  - {nome: a, tipo: ftp, url: https://a.com}\n", "noticias/a"),
        ("noticias:\n  - {nome: a, tipo: rss, url: a.com}\n", "noticias/a"),
        ("noticias:\n  - {nome: A B, tipo: rss, url: https://a.com}\n", "noticias/A B"),
        ("noticias:\n  - {nome: a, tipo: rss, url: https://a.com, limite: 500}\n", "noticias/a"),
        ("noticias:\n  - {nome: a, tipo: rss, url: https://a.com, extra: 1}\n", "noticias/a"),
        ("esportes:\n  - {nome: a, tipo: rss, url: https://a.com}\n", "esportes/a"),
        (
            "noticias:\n  - {nome: a, tipo: rss, url: https://a.com}\n"
            "  - {nome: a, tipo: rss, url: https://b.com}\n",
            "repetidos: a",
        ),
    ],
)
def test_fontes_invalidas(tmp_path: Path, conteudo: str, trecho_do_erro: str) -> None:
    with pytest.raises(config.ErroConfiguracao, match=trecho_do_erro):
        config.carregar_fontes_validas(_yaml(tmp_path, conteudo))


def test_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _limpar_ambiente(monkeypatch)
    assert config.ler_ambiente().user_agent == "RadarPessoal/0.1"
    monkeypatch.setenv("RADAR_CONTATO", "alguem+radar@exemplo.com")
    cfg = config.ler_ambiente()
    assert cfg.user_agent == "RadarPessoal/0.1 (+alguem+radar@exemplo.com)"
    assert "alguem" not in repr(cfg)
