"""Modelos de dados compartilhados entre coletores, IA e banco."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

Modulo = Literal["noticias", "estagios", "concursos"]
StatusItem = Literal["pendente", "processado", "descartado", "erro"]

LIMITE_TEXTO = 4000


def normalizar_url(url: str) -> str:
    """Normaliza uma URL para deduplicação.

    - remove espaços nas pontas, fragmento (#...) e parâmetros utm_*;
    - deixa esquema e domínio em minúsculas;
    - ordena os parâmetros restantes, para que a ordem não gere duplicatas.
    """
    partes = urlsplit(url.strip())
    parametros = [
        (chave, valor)
        for chave, valor in parse_qsl(partes.query, keep_blank_values=True)
        if not chave.lower().startswith("utm_")
    ]
    parametros.sort()
    return urlunsplit(
        (
            partes.scheme.lower(),
            partes.netloc.lower(),
            partes.path or "/",
            urlencode(parametros, doseq=True),
            "",
        )
    )


def gerar_id_unico(url: str) -> str:
    """sha256 (hex) da URL normalizada."""
    return hashlib.sha256(normalizar_url(url).encode("utf-8")).hexdigest()


class Item(BaseModel):
    """Item normalizado que todo coletor devolve."""

    model_config = ConfigDict(str_strip_whitespace=True)

    modulo: Modulo
    fonte: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    url: str = Field(min_length=1)
    publicado_em: datetime | None = None
    texto: str = ""
    id_unico: str = ""

    @field_validator("texto")
    @classmethod
    def _truncar_texto(cls, valor: str) -> str:
        return valor[:LIMITE_TEXTO]

    @field_validator("publicado_em")
    @classmethod
    def _garantir_fuso(cls, valor: datetime | None) -> datetime | None:
        if valor is not None and valor.tzinfo is None:
            return valor.replace(tzinfo=UTC)
        return valor

    @model_validator(mode="after")
    def _calcular_id_unico(self) -> Item:
        if not self.id_unico:
            self.id_unico = gerar_id_unico(self.url)
        return self

    def para_banco(self) -> dict[str, Any]:
        """Dicionário pronto para inserir na tabela `itens`."""
        return self.model_dump(mode="json")


TipoFonte = Literal["rss", "github", "iel"]  # pdf entra no bloco 5


class Fonte(BaseModel):
    """Uma fonte do fontes.yaml."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    modulo: Modulo
    nome: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    tipo: TipoFonte
    url: str = Field(pattern=r"^https?://")
    janela_horas: int = Field(default=72, gt=0)
    limite: int = Field(default=50, gt=0, le=50)


class ItemPendente(BaseModel):
    """Item já gravado que aguarda triagem pela IA."""

    id: int
    modulo: Modulo
    fonte: str
    titulo: str
    url: str
    texto: str | None = None
    tentativas_ia: int = 0


class ItemResumo(BaseModel):
    """Item triado e ainda não enviado, pronto para entrar no resumo diário."""

    id: int
    modulo: Modulo
    fonte: str
    titulo: str
    url: str
    publicado_em: datetime | None = None
    nota: int
    resumo: str | None = None
    tags: list[str] = Field(default_factory=list)
    prazo: date | None = None
    campos: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags", "campos", mode="before")
    @classmethod
    def _nulos(cls, valor: object, info: ValidationInfo) -> object:
        if valor:
            return valor
        return [] if info.field_name == "tags" else {}


class CamposEstagio(BaseModel):
    """Campos extraídos de uma vaga. Tudo opcional: o que não está no texto fica nulo."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    empresa: str | None = None
    area: str | None = None
    cidade: str | None = None
    remoto: bool | None = None
    bolsa: str | None = None
    requisitos: list[str] = Field(default_factory=list, max_length=10)
    link_inscricao: str | None = None

    @field_validator("empresa", "area", "cidade", "bolsa", "link_inscricao", mode="before")
    @classmethod
    def _vazio_vira_nulo(cls, valor: object) -> object:
        if isinstance(valor, str) and valor.strip().lower() in ("", "null", "none", "n/a"):
            return None
        return valor

    @field_validator("requisitos", mode="before")
    @classmethod
    def _requisitos_nulos(cls, valor: object) -> object:
        return valor or []

    @field_validator("link_inscricao")
    @classmethod
    def _link_http(cls, valor: str | None) -> str | None:
        return valor if valor and valor.startswith(("http://", "https://")) else None


class Resultado(BaseModel):
    """Triagem de um item, como devolvida pela IA e validada."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    nota: int = Field(ge=0, le=10)
    resumo: str = Field(min_length=1, max_length=600)
    tags: list[str] = Field(default_factory=list, max_length=8)
    descartar: bool = False
    campos: dict[str, Any] = Field(default_factory=dict)
    prazo: date | None = None

    @field_validator("tags")
    @classmethod
    def _normalizar_tags(cls, tags: list[str]) -> list[str]:
        vistas: list[str] = []
        for tag in tags:
            limpa = tag.strip().lower()
            if limpa and limpa not in vistas:
                vistas.append(limpa)
        return vistas

    @field_validator("prazo", mode="before")
    @classmethod
    def _prazo_vazio(cls, valor: object) -> object:
        if isinstance(valor, str) and valor.strip().lower() in ("", "null", "none"):
            return None
        return valor

    @property
    def status(self) -> StatusItem:
        return "descartado" if self.descartar else "processado"
