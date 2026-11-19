# MordeNews

Radar pessoal de informação: coleta notícias tech, vagas de estágio e editais de concurso, faz a triagem com IA e entrega um resumo no Telegram.

Fluxo: `fontes → coletores agendados → triagem por IA → banco (Supabase) → Telegram / portal web`.

Regras de desenvolvimento e o plano por blocos estão em [CLAUDE.md](CLAUDE.md); o estado atual fica em [docs/progresso.md](docs/progresso.md). Para montar o ambiente em outra máquina e retomar o trabalho, veja [docs/retomar.md](docs/retomar.md).

## Começando

Pré-requisito: [uv](https://docs.astral.sh/uv/) (ele instala o Python 3.12 sozinho).

```powershell
uv sync                     # cria .venv e instala dependências
copy .env.example .env      # depois preencha as variáveis
uv run radar teste-banco    # valida a conexão com o Supabase
```

## Qualidade

```powershell
uv run ruff check .
uv run ruff format .
uv run pytest
```

Os testes não acessam a rede: o Supabase é simulado em memória (`tests/conftest.py`).
