# astronomIA - Agentic Galaxy Analysis Backend

Backend profesional y escalable para un chatbot agéntico de análisis de galaxias.
`n8n` vive fuera de este repositorio y consumirá el endpoint HTTP `POST /analyze`.

## Stack y objetivos

- **API:** FastAPI
- **Arquitectura:** modular estilo DDD (`domain` / `application` / `infrastructure` / `interfaces`)
- **Core DS:** `packages/galaxy_core` (sin dependencias de LangChain)
- **Capa agente:** `packages/galaxy_agent` (tools + orquestador + scaffolding LangChain)
- **Observabilidad:** logging JSON estructurado + scaffolding LangSmith
- **Infra:** Docker CPU + opción GPU (NVIDIA)

## Estructura

```text
.
├── apps/
│   └── api/
├── packages/
│   ├── galaxy_core/
│   └── galaxy_agent/
├── tests/
├── artifacts/
├── notebooks/
├── scripts/
├── docs/
└── docker/
```

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestor de entorno/dependencias)

## Levantar en local

1. Crear `.env` desde el ejemplo:

   ```bash
   cp .env.example .env
   ```

2. Instalar dependencias:

   ```bash
   make install
   ```

3. Ejecutar API:

   ```bash
   make run
   ```

   También funciona directamente:

   ```bash
   uv run uvicorn apps.api.main:app --reload
   ```

## Tests, lint y type-check

```bash
make test
make lint
make format
make typecheck
```

## Endpoints MVP

- `GET /health` -> `{"status":"ok"}`
- `POST /analyze`

### Request `/analyze`

```json
{
  "request_id": "req-001",
  "target": { "name": "NGC 1300" },
  "task": "morphology_summary",
  "image_url": null,
  "options": {}
}
```

### Response `/analyze` (shape)

```json
{
  "request_id": "req-001",
  "status": "success",
  "summary": "Detected galaxy-like structure with area ~...",
  "results": {},
  "artifacts": [{ "type": "mask", "path": "artifacts/req-001/mask.png" }],
  "provenance": {
    "timestamp": "2026-01-01T00:00:00+00:00",
    "versions": {
      "galaxy_core": "0.1.0",
      "galaxy_agent": "0.1.0"
    }
  },
  "warnings": []
}
```

## Ejemplos curl

Health:

```bash
curl -s http://localhost:8000/health
```

Analyze (con API key):

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "request_id":"req-001",
    "target":{"name":"NGC 1300"},
    "task":"morphology_summary",
    "options":{}
  }'
```

Para desarrollo sin API key, usar en `.env`:

```env
REQUIRE_API_KEY=false
```

## Docker

Útil en Windows (sin instalar Python) o para tener el mismo entorno que en producción. Desde la carpeta `docker/`:

### CPU

```bash
docker compose -f docker-compose.yml up --build
```

La API queda en `http://localhost:8000`. Los artifacts se guardan en `../artifacts` (volumen montado).

### Ejecutar tests dentro del contenedor

Para probar resolve/fetch/analyze sin Python en el host (p. ej. en Windows):

```bash
cd docker
docker compose -f docker-compose.yml run --rm api python scripts/test_analyze_multi.py --sdss-only
```

Todos los casos (incluido SkyView):

```bash
docker compose -f docker-compose.yml run --rm api python scripts/test_analyze_multi.py
```

Si en tu red hay problemas de SSL (proxy corporativo), crea o edita `.env` y añade `REQUESTS_VERIFY_SSL=false`.

### GPU (NVIDIA opcional)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

## Variables de entorno

Ver `.env.example`:

- `API_KEY`
- `REQUIRE_API_KEY`
- `ARTIFACT_DIR`
- `LOG_LEVEL`
- `LANGSMITH_API_KEY` (opcional)
- `LANGSMITH_TRACING` (opcional)
- `REQUESTS_VERIFY_SSL` (opcional, default `true`; poner `false` si hay errores de certificado SSL con SESAME/SkyView)
- `SKYVIEW_TIMEOUT` (opcional, segundos; default 240; subir si SkyView hace timeout)
