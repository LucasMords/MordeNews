"""Montagem e envio do resumo diário por e-mail (SMTP com SSL, biblioteca padrão)."""

from __future__ import annotations

import logging
import smtplib
import ssl
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape

from radar.modelos import ItemResumo

log = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 30
NOME_REMETENTE = "MordeNews"
BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019
NOTA_DESTAQUE = 9

TITULOS_MODULO = {"noticias": "Notícias", "estagios": "Estágios", "concursos": "Concursos"}
ORDEM_MODULO = ("concursos", "estagios", "noticias")  # oportunidades com prazo primeiro


class ErroEnvio(RuntimeError):
    """Falha ao entregar o e-mail (login, conexão ou recusa do servidor)."""


@dataclass(frozen=True)
class Mensagem:
    assunto: str
    texto: str
    html: str


@dataclass(frozen=True)
class Assunto:
    """Uma entrada do resumo: o item principal e, se houver, a mesma notícia em outras fontes."""

    principal: ItemResumo
    repetidos: tuple[ItemResumo, ...] = ()

    @property
    def nota(self) -> int:
        return self.principal.nota

    @property
    def itens(self) -> tuple[ItemResumo, ...]:
        return (self.principal, *self.repetidos)


Grupos = list[tuple[str, list[Assunto]]]


# ------------------------------------------------------------------ formatação


def _data(valor: datetime | date | None) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        valor = valor.astimezone(BRASILIA).date()
    return valor.strftime("%d/%m/%Y")


def _por_modulo(assuntos: Sequence[Assunto]) -> Grupos:
    grupos: Grupos = []
    for modulo in ORDEM_MODULO:
        do_modulo = sorted(
            (a for a in assuntos if a.principal.modulo == modulo),
            key=lambda a: (-a.nota, -a.principal.id),
        )
        if do_modulo:
            grupos.append((modulo, do_modulo))
    return grupos


def _titulo_email(assuntos: Sequence[Assunto], hoje: date) -> str:
    destaques = sum(a.nota >= NOTA_DESTAQUE for a in assuntos)
    plural = "item" if len(assuntos) == 1 else "itens"
    extra = f", {destaques} em destaque" if destaques else ""
    return f"{NOME_REMETENTE} {hoje:%d/%m}: {len(assuntos)} {plural}{extra}"


def _rodape(nota_minima: int, fora: int, nota_minima_estagios: int | None = None) -> str:
    texto = f"Itens com nota {nota_minima} ou mais, ordenados por nota."
    if nota_minima_estagios is not None and nota_minima_estagios != nota_minima:
        if nota_minima_estagios <= 0:
            texto += " Vagas de estágio aparecem com qualquer nota (as fora de TI são descartadas)."
        else:
            texto += f" Vagas de estágio aparecem a partir da nota {nota_minima_estagios}."
    if fora:
        texto += f" Outros {fora} itens com nota suficiente ficaram de fora pelo limite diário."
    return texto


def montar_mensagem(
    assuntos: Sequence[Assunto | ItemResumo],
    hoje: date,
    *,
    nota_minima: int,
    fora: int = 0,
    nota_minima_estagios: int | None = None,
) -> Mensagem:
    """Monta o resumo agrupado por módulo e ordenado por nota, em HTML e texto puro."""
    normalizados = [a if isinstance(a, Assunto) else Assunto(a) for a in assuntos]
    grupos = _por_modulo(normalizados)
    rodape = _rodape(nota_minima, fora, nota_minima_estagios)
    return Mensagem(
        assunto=_titulo_email(normalizados, hoje),
        texto=_montar_texto(grupos, hoje, rodape),
        html=_montar_html(grupos, hoje, rodape),
    )


def _linha_meta(item: ItemResumo) -> str:
    partes = [item.fonte]
    if item.publicado_em:
        partes.append(_data(item.publicado_em))
    return " · ".join(partes)


def _linha_vaga(item: ItemResumo) -> str | None:
    """Empresa · local · bolsa, para vagas. Só o que a triagem extraiu do texto."""
    campos = item.campos
    if item.modulo != "estagios" or not campos:
        return None
    local = campos.get("cidade")
    if campos.get("remoto") is True:
        local = f"{local} (remoto)" if local else "Remoto"
    partes = [campos.get("empresa"), local, campos.get("bolsa")]
    texto = " · ".join(str(p) for p in partes if p)
    return texto or None


def _montar_texto(grupos: Grupos, hoje: date, rodape: str) -> str:
    linhas = [f"{NOME_REMETENTE} — resumo de {_data(hoje)}", ""]
    for modulo, assuntos in grupos:
        linhas += [f"== {TITULOS_MODULO[modulo]} ({len(assuntos)}) ==", ""]
        for assunto in assuntos:
            item = assunto.principal
            linhas.append(f"[{item.nota}] {item.titulo}")
            linhas.append(f"    {_linha_meta(item)}")
            if vaga := _linha_vaga(item):
                linhas.append(f"    {vaga}")
            if item.resumo:
                linhas.append(f"    {item.resumo}")
            if item.prazo:
                linhas.append(f"    PRAZO: {_data(item.prazo)}")
            linhas.append(f"    {item.url}")
            if assunto.repetidos:
                outras = ", ".join(f"{r.fonte} ({r.url})" for r in assunto.repetidos)
                linhas.append(f"    Também em: {outras}")
            linhas.append("")
    linhas += ["--", rodape]
    return "\n".join(linhas)


_ESTILO_NOTA = (
    "display:inline-block;min-width:22px;padding:1px 6px;border-radius:10px;"
    "font-size:12px;font-weight:bold;text-align:center;color:#fff;background:{cor};"
)


def _cor_nota(nota: int) -> str:
    if nota >= NOTA_DESTAQUE:
        return "#b42318"
    if nota >= 7:
        return "#c4320a"
    return "#667085"


def _link(url: str, texto: str, estilo: str = "color:#1849a9;") -> str:
    return f'<a href="{escape(url, quote=True)}" style="{estilo}">{escape(texto)}</a>'


def _assunto_html(assunto: Assunto) -> str:
    item = assunto.principal
    nota = f'<span style="{_ESTILO_NOTA.format(cor=_cor_nota(item.nota))}">{item.nota}</span>'
    titulo = _link(item.url, item.titulo, "color:#1849a9;font-weight:600;text-decoration:none;")
    blocos = [
        f'<div style="margin:0 0 4px 0;">{nota} {titulo}</div>',
        f'<div style="color:#667085;font-size:12px;margin:0 0 4px 0;">'
        f"{escape(_linha_meta(item))}</div>",
    ]
    if vaga := _linha_vaga(item):
        blocos.append(f'<div style="margin:0 0 4px 0;font-weight:600;">{escape(vaga)}</div>')
    if item.resumo:
        blocos.append(f'<div style="margin:0 0 4px 0;">{escape(item.resumo)}</div>')
    if item.prazo:
        blocos.append(
            f'<div style="color:#b42318;font-weight:bold;">Prazo: {escape(_data(item.prazo))}</div>'
        )
    if assunto.repetidos:
        outras = ", ".join(_link(r.url, r.fonte) for r in assunto.repetidos)
        blocos.append(f'<div style="color:#667085;font-size:12px;">Também em: {outras}</div>')
    return f'<div style="padding:10px 0;border-bottom:1px solid #eaecf0;">{"".join(blocos)}</div>'


def _montar_html(grupos: Grupos, hoje: date, rodape: str) -> str:
    secoes = []
    for modulo, assuntos in grupos:
        titulo = escape(f"{TITULOS_MODULO[modulo]} ({len(assuntos)})")
        corpo = "".join(_assunto_html(a) for a in assuntos)
        secoes.append(
            f'<h2 style="font-size:16px;margin:24px 0 4px 0;color:#101828;">{titulo}</h2>{corpo}'
        )
    return (
        '<!doctype html><html lang="pt-BR"><body style="margin:0;padding:16px;background:#f9fafb;">'
        '<div style="max-width:640px;margin:0 auto;background:#fff;padding:16px 20px;'
        "border-radius:8px;font-family:Arial,Helvetica,sans-serif;font-size:14px;"
        'line-height:1.45;color:#344054;">'
        f'<h1 style="font-size:20px;margin:0;color:#101828;">{NOME_REMETENTE}</h1>'
        f'<div style="color:#667085;">Resumo de {escape(_data(hoje))}</div>'
        f"{''.join(secoes)}"
        f'<p style="color:#667085;font-size:12px;margin-top:24px;">{escape(rodape)}</p>'
        "</div></body></html>"
    )


# ------------------------------------------------------------------------ envio


def montar_email(mensagem: Mensagem, remetente: str, destino: str) -> EmailMessage:
    email = EmailMessage()
    email["Subject"] = mensagem.assunto
    email["From"] = formataddr((NOME_REMETENTE, remetente))
    email["To"] = destino
    email["Message-ID"] = make_msgid(domain=remetente.split("@")[-1])
    email.set_content(mensagem.texto)
    email.add_alternative(mensagem.html, subtype="html")
    return email


def enviar(
    mensagem: Mensagem, *, remetente: str, senha_app: str, destino: str, host: str, porta: int
) -> None:
    """Envia por SMTP com SSL. Erros viram ErroEnvio, sem expor a senha."""
    email = montar_email(mensagem, remetente, destino)
    try:
        with smtplib.SMTP_SSL(
            host, porta, timeout=TIMEOUT_SEGUNDOS, context=ssl.create_default_context()
        ) as smtp:
            smtp.login(remetente, senha_app)
            smtp.send_message(email)
    except smtplib.SMTPAuthenticationError as erro:
        raise ErroEnvio(
            "login SMTP recusado: confira EMAIL_REMETENTE e EMAIL_SENHA_APP "
            "(precisa ser uma senha de app, com verificação em 2 etapas ativa)"
        ) from erro
    except (smtplib.SMTPException, OSError) as erro:
        raise ErroEnvio(f"falha ao enviar o e-mail: {type(erro).__name__}: {erro}") from erro
    log.info("e-mail enviado: %s", mensagem.assunto)
