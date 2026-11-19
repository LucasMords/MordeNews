import smtplib
from datetime import UTC, date, datetime
from email import message_from_bytes
from typing import Any, ClassVar

import pytest

from radar.entrega import correio
from radar.modelos import ItemResumo

HOJE = date(2026, 11, 19)


def _item(id_: int, nota: int, **extra: Any) -> ItemResumo:
    dados: dict[str, Any] = {
        "id": id_,
        "modulo": "noticias",
        "fonte": "tecnoblog",
        "titulo": f"Notícia {id_}",
        "url": f"https://exemplo.com/{id_}",
        "publicado_em": datetime(2026, 11, 19, 2, 30, tzinfo=UTC),  # 18/11 23:30 em Brasília
        "nota": nota,
        "resumo": f"Resumo {id_}.",
        "tags": ["ia"],
    }
    dados.update(extra)
    return ItemResumo.model_validate(dados)


def test_assunto_conta_itens_e_destaques() -> None:
    mensagem = correio.montar_mensagem([_item(1, 9), _item(2, 6)], HOJE, nota_minima=6)
    assert mensagem.assunto == "MordeNews 19/11: 2 itens, 1 em destaque"
    um = correio.montar_mensagem([_item(1, 7)], HOJE, nota_minima=6)
    assert um.assunto == "MordeNews 19/11: 1 item"


def test_agrupa_por_modulo_e_ordena_por_nota() -> None:
    itens = [
        _item(1, 6),
        _item(2, 9),
        _item(3, 7, modulo="concursos", titulo="Edital IFTO", prazo=date(2026, 12, 1)),
    ]
    texto = correio.montar_mensagem(itens, HOJE, nota_minima=6).texto
    # concursos (com prazo) vêm antes de notícias; dentro do módulo, maior nota primeiro
    assert texto.index("== Concursos (1) ==") < texto.index("== Notícias (2) ==")
    assert texto.index("[9] Notícia 2") < texto.index("[6] Notícia 1")
    assert "PRAZO: 01/12/2026" in texto


def test_texto_tem_link_fonte_data_e_resumo() -> None:
    texto = correio.montar_mensagem([_item(1, 8)], HOJE, nota_minima=6).texto
    assert "https://exemplo.com/1" in texto
    assert "tecnoblog · 18/11/2026" in texto  # data convertida para o horário de Brasília
    assert "Resumo 1." in texto


def test_html_escapa_conteudo_externo() -> None:
    perigoso = _item(
        1,
        8,
        titulo='<script>alert("x")</script> & cia',
        resumo="1 < 2 & 3 > 2",
        url='https://exemplo.com/?a=1&b="2"',
    )
    html = correio.montar_mensagem([perigoso], HOJE, nota_minima=6).html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; cia" in html
    assert "1 &lt; 2 &amp; 3 &gt; 2" in html
    assert 'href="https://exemplo.com/?a=1&amp;b=&quot;2&quot;"' in html


def test_rodape_informa_itens_de_fora() -> None:
    mensagem = correio.montar_mensagem([_item(1, 8)], HOJE, nota_minima=6, fora=12)
    assert "Outros 12 itens" in mensagem.texto
    assert "Outros 12 itens" in mensagem.html
    sem_fora = correio.montar_mensagem([_item(1, 8)], HOJE, nota_minima=6)
    assert "Outros" not in sem_fora.texto


def test_item_sem_resumo_nem_data() -> None:
    item = _item(1, 7, resumo=None, publicado_em=None)
    texto = correio.montar_mensagem([item], HOJE, nota_minima=6).texto
    assert "    tecnoblog\n" in texto


def test_email_tem_texto_e_html() -> None:
    mensagem = correio.montar_mensagem([_item(1, 8)], HOJE, nota_minima=6)
    email = correio.montar_email(mensagem, "robo@exemplo.com", "eu@exemplo.com")
    lido = message_from_bytes(email.as_bytes())
    assert lido["To"] == "eu@exemplo.com"
    assert "MordeNews" in lido["From"] and "robo@exemplo.com" in lido["From"]
    tipos = [parte.get_content_type() for parte in lido.walk()]
    assert "text/plain" in tipos and "text/html" in tipos


# ------------------------------------------------------------------- envio SMTP


class SmtpFalso:
    instancias: ClassVar[list["SmtpFalso"]] = []
    falhar_login: ClassVar[bool] = False

    def __init__(self, host: str, porta: int, **opcoes: Any) -> None:
        self.host, self.porta, self.opcoes = host, porta, opcoes
        self.login_feito: tuple[str, str] | None = None
        self.enviadas: list[Any] = []
        SmtpFalso.instancias.append(self)

    def __enter__(self) -> "SmtpFalso":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def login(self, usuario: str, senha: str) -> None:
        if SmtpFalso.falhar_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.login_feito = (usuario, senha)

    def send_message(self, mensagem: Any) -> None:
        self.enviadas.append(mensagem)


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> type[SmtpFalso]:
    SmtpFalso.instancias = []
    SmtpFalso.falhar_login = False
    monkeypatch.setattr(correio.smtplib, "SMTP_SSL", SmtpFalso)
    return SmtpFalso


def _enviar() -> None:
    mensagem = correio.montar_mensagem([_item(1, 8)], HOJE, nota_minima=6)
    correio.enviar(
        mensagem,
        remetente="robo@exemplo.com",
        senha_app="senha",
        destino="eu@exemplo.com",
        host="smtp.gmail.com",
        porta=465,
    )


def test_enviar_faz_login_e_envia(smtp: type[SmtpFalso]) -> None:
    _enviar()
    [conexao] = smtp.instancias
    assert (conexao.host, conexao.porta, conexao.opcoes["timeout"]) == ("smtp.gmail.com", 465, 30)
    assert conexao.login_feito == ("robo@exemplo.com", "senha")
    assert len(conexao.enviadas) == 1


def test_login_recusado_vira_erro_claro_sem_senha(smtp: type[SmtpFalso]) -> None:
    smtp.falhar_login = True
    with pytest.raises(correio.ErroEnvio, match="senha de app") as info:
        _enviar()
    assert "senha'" not in str(info.value)


def test_falha_de_conexao_vira_erro_envio(monkeypatch: pytest.MonkeyPatch) -> None:
    def sem_rede(*_: Any, **__: Any) -> None:
        raise OSError("rede indisponível")

    monkeypatch.setattr(correio.smtplib, "SMTP_SSL", sem_rede)
    with pytest.raises(correio.ErroEnvio, match="rede indisponível"):
        _enviar()
