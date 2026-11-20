"""Agrupa a mesma notícia vinda de fontes diferentes, com regras determinísticas (sem IA).

Dois itens são o mesmo assunto quando:
- ambos citam CVEs e têm pelo menos um em comum (CVEs diferentes = falhas diferentes); ou
- ao menos um não cita CVE e:
  - os títulos compartilham um "nome" com letras e números (ex.: java4shell, log4shell); ou
  - os títulos têm ao menos MIN_COMUNS palavras significativas em comum, cobrindo
    LIMIAR_TITULO das palavras do título mais curto.
A relação é transitiva (A~B e B~C → A, B e C juntos).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime

from radar.entrega.correio import Assunto
from radar.modelos import ItemResumo

# Vagas e concursos só pelas regras próprias de `_mesma_vaga` e `_mesmo_concurso`: "Estágio em
# Administração" de duas empresas são duas vagas.
MODULOS_AGRUPAVEIS = frozenset({"noticias"})
LIMIAR_TITULO = 0.6
MIN_COMUNS = 2
_CVE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_PALAVRA = re.compile(r"[a-z0-9]+")

# Palavras frequentes que não ajudam a identificar o assunto (PT e EN), já sem acento.
_VAZIAS = frozenset(
    """
    a o as os um uma uns umas de da do das dos em no na nos nas por para pra com sem sobre
    e ou que se ao aos como mais menos ja nao sim seu sua seus suas pode podem novo nova novos
    novas apos ate entre the an of to in on for with and or by from at is are was be as its it
    new how why what your you this that after into over now not can will when where which who
    has have had about all just out its their they our
    """.split()  # noqa: SIM905 — lista longa fica mais legível como texto
)


# Palavras de modalidade e contrato em títulos de vaga; não identificam o cargo.
_MODALIDADE = frozenset(
    [
        "remoto",
        "remota",
        "remote",
        "hibrido",
        "hibrida",
        "presencial",
        "brasil",
        "vaga",
        "vagas",
        "clt",
        "pj",
    ]
)


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


def palavras(titulo: str) -> frozenset[str]:
    """Palavras significativas do título: minúsculas, sem acento, sem palavras vazias."""
    return frozenset(
        p for p in _PALAVRA.findall(_sem_acento(titulo)) if len(p) >= 3 and p not in _VAZIAS
    )


def nomes(titulo: str) -> frozenset[str]:
    """Palavras com letras e números (5+ caracteres), típicas de nomes próprios de falhas e
    produtos: java4shell, log4shell, base64. São quase uma assinatura do assunto."""
    return frozenset(
        p
        for p in palavras(titulo)
        if len(p) >= 5 and any(c.isdigit() for c in p) and any(c.isalpha() for c in p)
    )


def cves(item: ItemResumo) -> frozenset[str]:
    return frozenset(c.upper() for c in _CVE.findall(f"{item.titulo} {item.resumo or ''}"))


def _parecidos(a: frozenset[str], b: frozenset[str]) -> bool:
    """Ao menos MIN_COMUNS palavras em comum, cobrindo LIMIAR_TITULO do título mais curto."""
    comuns = len(a & b)
    if comuns < MIN_COMUNS:
        return False
    return comuns / min(len(a), len(b)) >= LIMIAR_TITULO


def _empresa(item: ItemResumo) -> str:
    return " ".join(_PALAVRA.findall(_sem_acento(str(item.campos.get("empresa") or ""))))


def _cargo(item: ItemResumo, titulo: frozenset[str]) -> frozenset[str]:
    """Palavras do título que descrevem o cargo: sem empresa, cidade nem modalidade."""
    contexto = palavras(f"{item.campos.get('empresa') or ''} {item.campos.get('cidade') or ''}")
    return titulo - contexto - _MODALIDADE


def _mesma_vaga(
    a: ItemResumo, b: ItemResumo, titulo_a: frozenset[str], titulo_b: frozenset[str]
) -> bool:
    """A mesma vaga repostada em outra fonte (ex.: dois repositórios de vagas do GitHub).

    Exige fontes diferentes, a mesma empresa e o mesmo cargo no título. Na mesma fonte nunca
    junta: "Educação Física - Licenciatura" e "- Bacharelado" do SESI são duas vagas. Empresa,
    cidade e modalidade não contam como semelhança: "DevOps Sênior / Proativa RH - São Paulo" e
    "QA Manager na Proativa RH [São Paulo]" são duas vagas.
    """
    if a.modulo != "estagios" or b.modulo != "estagios" or a.fonte == b.fonte:
        return False
    empresa = _empresa(a)
    if not empresa or empresa != _empresa(b):
        return False
    return _parecidos(_cargo(a, titulo_a), _cargo(b, titulo_b))


_GENERICOS = frozenset(
    ["prefeitura", "camara", "municipal", "municipio", "estado", "estadual", "secretaria",
     "governo", "fundo"]
)  # fmt: skip


def _orgao(item: ItemResumo) -> list[str]:
    """Palavras significativas do órgão, na ordem (a primeira diz o tipo: prefeitura, câmara...)."""
    return [
        p
        for p in _PALAVRA.findall(_sem_acento(str(item.campos.get("orgao") or "")))
        if len(p) >= 3 and p not in _VAZIAS
    ]


def _mesmo_concurso(a: ItemResumo, b: ItemResumo) -> bool:
    """O mesmo concurso publicado por fontes diferentes (ex.: PCI e Concursos no Brasil).

    Exige fontes diferentes e o mesmo órgão: as mesmas palavras em qualquer ordem ("IFG -
    Instituto Federal..." = "Instituto Federal... (IFG)"), ou o mesmo tipo de órgão
    ("prefeitura" ≠ "câmara", mesmo na mesma cidade) com nomes parecidos.

    Prazos diferentes indicam seleções diferentes do mesmo órgão (ex.: estágio e Jovem Aprendiz
    da Saneago); sem prazo em um dos dois, vale só o órgão.
    """
    if a.modulo != "concursos" or b.modulo != "concursos" or a.fonte == b.fonte:
        return False
    if a.prazo and b.prazo and a.prazo != b.prazo:
        return False
    orgao_a, orgao_b = _orgao(a), _orgao(b)
    if not orgao_a or not orgao_b:
        return False
    if set(orgao_a) == set(orgao_b):
        return True
    # Palavras genéricas não identificam o órgão: "Prefeitura e Câmara de Faina" e "Prefeitura e
    # Câmara de Campo Limpo" só têm em comum "prefeitura" e "câmara".
    nome_a, nome_b = frozenset(orgao_a) - _GENERICOS, frozenset(orgao_b) - _GENERICOS
    if orgao_a[0] != orgao_b[0] or not nome_a or not nome_b:
        return False
    return nome_a == nome_b or _parecidos(nome_a, nome_b)


def _ordem(item: ItemResumo) -> tuple[int, datetime, int]:
    return (item.nota, item.publicado_em or datetime.min.replace(tzinfo=UTC), item.id)


def agrupar(itens: Sequence[ItemResumo]) -> list[Assunto]:
    """Devolve um Assunto por notícia distinta, com o item de maior nota como principal.

    Notícias são agrupadas pelo assunto; vagas, só quando são a mesma vaga em outra fonte.
    Nunca junta módulos diferentes. A lista sai ordenada por nota.
    """
    pais = list(range(len(itens)))

    def raiz(i: int) -> int:
        while pais[i] != i:
            pais[i] = pais[pais[i]]
            i = pais[i]
        return i

    titulos = [palavras(i.titulo) for i in itens]
    proprios = [nomes(i.titulo) for i in itens]
    codigos = [cves(i) for i in itens]
    for a in range(len(itens)):
        for b in range(a + 1, len(itens)):
            if _mesma_vaga(itens[a], itens[b], titulos[a], titulos[b]) or _mesmo_concurso(
                itens[a], itens[b]
            ):
                pais[raiz(b)] = raiz(a)
                continue
            if itens[a].modulo != itens[b].modulo or itens[a].modulo not in MODULOS_AGRUPAVEIS:
                continue
            if codigos[a] and codigos[b]:
                # Os dois citam CVEs: só são o mesmo assunto se for a mesma falha. Títulos de
                # segurança repetem jargão ("falha crítica permite execução remota").
                mesmo = bool(codigos[a] & codigos[b])
            else:
                mesmo = bool(proprios[a] & proprios[b]) or _parecidos(titulos[a], titulos[b])
            if mesmo:
                pais[raiz(b)] = raiz(a)

    grupos: dict[int, list[ItemResumo]] = {}
    for indice, item in enumerate(itens):
        grupos.setdefault(raiz(indice), []).append(item)

    assuntos = []
    for membros in grupos.values():
        membros.sort(key=_ordem, reverse=True)
        principal, *repetidos = membros
        assuntos.append(Assunto(principal, tuple(repetidos)))
    assuntos.sort(key=lambda a: _ordem(a.principal), reverse=True)
    return assuntos
