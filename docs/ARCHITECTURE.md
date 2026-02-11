# Estructura del proyecto y guía de desarrollo

## Visión general

El repo es un **monorepo** con tres capas claras:

1. **API** (`apps/api`) — Entrada HTTP; solo recibe requests y delega en el agente.
2. **Agente** (`packages/galaxy_agent`) — Orquesta tareas, tools y LangChain; llama al core.
3. **Core DS** (`packages/galaxy_core`) — Lógica de análisis (segmentación, medidas, resumen); **sin LLM**.

Flujo de una petición:

```
Cliente/n8n  →  POST /analyze  →  apps.api.main  →  AgentRunner.run()
                                                    →  LangChainBackend (scaffold)
                                                    →  TaskOrchestrator.run()
                                                         →  tools (load_image, segment, measure…)
                                                              →  galaxy_core (BasicGalaxyAnalyzer)
                                                         →  ArtifactStore (guardar máscaras, reportes)
                                                    →  AnalyzeResponse
```

---

## Árbol y responsabilidades

```
astronomIA/
├── apps/
│   └── api/                    # Capa HTTP
│       ├── main.py             # App FastAPI, rutas /health y /analyze
│       ├── config.py           # Settings desde env (API_KEY, ARTIFACT_DIR, LOG_LEVEL…)
│       └── auth.py             # Verificación X-API-Key
│
├── packages/
│   ├── galaxy_core/            # Librería de data science (sin LangChain)
│   │   ├── domain/             # Contratos: GalaxyAnalyzer, SegmentationResult
│   │   ├── application/         # BasicGalaxyAnalyzer (segment, measure_basic, morphology_summary)
│   │   ├── infrastructure/     # create_synthetic_image, normalize_image
│   │   ├── analyzer.py         # Punto de entrada: reexporta BasicGalaxyAnalyzer, create_synthetic_image
│   │   └── domain.py          # Reexporta modelos de dominio
│   │
│   └── galaxy_agent/           # Capa agente (LangChain + orquestación)
│       ├── domain/             # Pydantic: AnalyzeRequest, AnalyzeResponse, Artifact, Provenance
│       ├── application/        # Reexports AgentRunner, TaskOrchestrator
│       ├── infrastructure/     # ArtifactStore, LangChainBackend, logging JSON
│       ├── interfaces/         # Reexports tools y schemas
│       ├── agent_runner.py     # Entrada: run(request) → response; usa orchestrator + langchain_backend
│       ├── orchestrator.py     # Ejecuta tools según request.task (segment | measure_basic | morphology_summary)
│       ├── tools.py            # load_image, tool_segment, tool_measure_basic, tool_morphology_summary, tool_generate_report
│       ├── artifacts.py        # Guardar máscaras/reportes en artifacts/<request_id>/
│       ├── langchain_backend.py # Scaffold: build_prompt, plan_tool_calls (sin LLM real aún)
│       ├── logging_utils.py    # JsonFormatter, setup_logging
│       └── models.py            # Reexporta domain.models
│
├── tests/                      # pytest
│   └── test_galaxy_core.py     # Tests del analyzer con imágenes sintéticas
│
├── notebooks/                  # Experimentos (vacío)
├── scripts/                    # Utilidades (vacío)
├── docker/                     # Dockerfile + compose CPU/GPU
├── pyproject.toml              # Dependencias, ruff, black, mypy, pytest
├── Makefile                    # run, test, lint, format, typecheck, install
└── .env.example                 # API_KEY, ARTIFACT_DIR, LOG_LEVEL, LANGSMITH_*
```

---

## Dónde desarrollar qué

| Objetivo | Dónde tocar |
|----------|--------------|
| **Nuevos endpoints** | `apps/api/main.py` |
| **Nueva config / env** | `apps/api/config.py` y `.env.example` |
| **Nueva lógica de análisis (DS)** | `packages/galaxy_core`: domain (contratos), application (analyzer), infrastructure (datos/sintéticos) |
| **Nuevos “tasks” o flujos** | `packages/galaxy_agent/orchestrator.py` y, si hace falta, `tools.py` |
| **Nuevas tools para el agente** | `packages/galaxy_agent/tools.py` (y registrar en orchestrator o en LangChain cuando lo uses) |
| **Integrar LLM real (LangChain)** | `packages/galaxy_agent/langchain_backend.py` y opcionalmente `agent_runner._prepare_llm_plan` |
| **Formato de respuesta / request** | `packages/galaxy_agent/domain/models.py` (Pydantic) |
| **Dónde se guardan artefactos** | `packages/galaxy_agent/artifacts.py` y config `ARTIFACT_DIR` |
| **Logs / observabilidad** | `packages/galaxy_agent/logging_utils.py`; LangSmith en config y en el backend |

Regla práctica: **galaxy_core** no debe importar LangChain ni FastAPI; **galaxy_agent** puede importar core y LangChain; **apps/api** solo importa agent (y config/auth).

---

## Cómo empezar a desarrollar

### 1. Entorno

```bash
# Clonar / abrir repo, luego:
cp .env.example .env
# Editar .env si quieres (p. ej. REQUIRE_API_KEY=false para dev)

make install
```

### 2. Levantar la API

```bash
make run
# o: uv run uvicorn apps.api.main:app --reload
```

- Health: `curl http://localhost:8000/health`
- Analyze: ver ejemplos en el README (header `X-API-Key` si `REQUIRE_API_KEY=true`).

### 3. Tests y calidad

```bash
make test    # pytest
make lint    # ruff
make format  # black
make typecheck  # mypy
```

Antes de commit, conviene:

```bash
make precommit
```

### 4. Flujo típico

- **Cambiar lógica de segmentación/medidas**
  → Editar `packages/galaxy_core/application/analyzer_service.py` (y domain si cambian contratos).
  → Añadir o ajustar tests en `tests/test_galaxy_core.py`.

- **Añadir un nuevo tipo de task**
  → En `packages/galaxy_agent/domain/models.py` ampliar el `Literal` de `task`.
  → En `packages/galaxy_agent/orchestrator.py` añadir el branch que ejecute las tools necesarias.

- **Conectar un modelo LangChain de verdad**
  → Implementar en `packages/galaxy_agent/langchain_backend.py` (prompt + tool-calling).
  → El orchestrator puede seguir siendo “determinista” por task o delegar pasos en el LLM según diseño.

- **Probar con imágenes reales**
  → En el JSON de `/analyze` pasar `"image_url": "https://..."`.
  → Si no pasas `image_url`, se usa una imagen sintética (`create_synthetic_image`).

---

## DDD en este repo

- **Domain**: tipos y contratos (protocols, Pydantic) sin dependencias de frameworks.
- **Application**: casos de uso (AgentRunner, TaskOrchestrator, BasicGalaxyAnalyzer).
- **Infrastructure**: implementaciones concretas (archivos, red, logging, LangChain client).
- **Interfaces**: adaptadores y reexports hacia “afuera” (tools, schemas HTTP).

Los módulos en la raíz de `galaxy_core` y `galaxy_agent` (p. ej. `analyzer.py`, `agent_runner.py`, `orchestrator.py`, `tools.py`) son los que contienen la lógica; las carpetas `domain/`, `application/`, `infrastructure/`, `interfaces/` organizan y reexportan para mantener las capas claras.
