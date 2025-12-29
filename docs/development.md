# Desarrollo

Guía para desarrolladores que quieran contribuir a Cortex o entender su arquitectura interna.

---

## Configuración del Entorno

### Requisitos

| Herramienta | Versión | Propósito               |
| ----------- | ------- | ----------------------- |
| Python      | 3.11+   | Backend                 |
| Node.js     | 18+     | Frontend                |
| Docker      | 24+     | Servicios de desarrollo |
| Git         | 2.30+   | Control de versiones    |

### Setup Inicial

```bash
# 1. Clonar repositorio
git clone https://github.com/DeepRatAI/cortex-knowledge-assistant.git
cd cortex-knowledge-assistant

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias de desarrollo
pip install -e ".[dev]"

# 4. Verificar instalación
pytest tests/ -v
```

### Variables de Desarrollo

```bash
# Configuración mínima para desarrollo
export DATABASE_URL=sqlite:///./dev_cortex.db
export CKA_LLM_PROVIDER=Fake
export JWT_SECRET_KEY=dev-secret-key-for-testing-only
export CKA_LOG_LEVEL=DEBUG
```

### Iniciar Servicios Auxiliares

```bash
# Iniciar solo Qdrant y Redis para desarrollo
docker compose up -d qdrant redis postgres

# Verificar que están corriendo
docker compose ps
```

### Iniciar API en Modo Desarrollo

```bash
# Con auto-reload
uvicorn src.cortex_ka.api.main:app --reload --host 0.0.0.0 --port 8088
```

### Iniciar UI en Modo Desarrollo

```bash
cd ui
npm install
npm run dev
# Acceder a http://localhost:5173
```

---

## Estructura del Proyecto

```
cortex-knowledge-assistant/
├── src/
│   └── cortex_ka/           # Código principal
│       ├── api/             # FastAPI endpoints
│       ├── application/     # Lógica de aplicación (RAG, DLP)
│       ├── domain/          # Modelos y puertos
│       ├── infrastructure/  # Adaptadores (Qdrant, HF, Redis)
│       ├── auth/            # Autenticación
│       ├── transactions/    # Dominio transaccional
│       ├── system/          # Setup, status, admin
│       ├── scripts/         # Ingesta, evaluación
│       ├── demos/           # Modo demo
│       ├── eval/            # Evaluación PII
│       └── maintenance/     # Mantenimiento
├── tests/                   # Tests unitarios e integración
├── ui/                      # Frontend React
├── docs/                    # Documentación
├── k8s/                     # Manifests Kubernetes
├── docker/                  # Dockerfiles
├── scripts/                 # Scripts de utilidad
├── pyproject.toml           # Configuración del proyecto
├── docker-compose.yml       # Compose principal
└── Makefile                 # Comandos útiles
```

---

## Testing

### Ejecutar Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Con coverage (requiere pytest-cov)
pytest tests/ -v --cov=src/cortex_ka --cov-report=html
open htmlcov/index.html
```

### Ejecutar Tests Específicos

```bash
# Un archivo específico
pytest tests/test_pii.py -v

# Un test específico
pytest tests/test_pii.py::TestRedactPii::test_redacts_dni -v

# Tests que coincidan con un patrón
pytest tests/ -k "pii" -v
```

### Estructura de Tests

| Archivo            | Propósito                                      |
| ------------------ | ---------------------------------------------- |
| `test_pii.py`      | Redacción de datos sensibles (DNI, CUIT, etc.) |
| `test_chunking.py` | Particionado semántico de documentos           |
| `test_models.py`   | Modelos de dominio (DocumentChunk, Answer)     |

### Tests con Docker

```bash
# Ejecutar tests en contenedor
docker compose -f docker/compose.dev.yml run --rm api pytest tests/ -v
```

---

## Estilo de Código

### Python (Backend)

Usamos las siguientes herramientas:

| Herramienta | Propósito       | Comando              |
| ----------- | --------------- | -------------------- |
| Black       | Formateo        | `black src/ tests/`  |
| isort       | Ordenar imports | `isort src/ tests/`  |
| Flake8      | Linting         | `flake8 src/ tests/` |
| MyPy        | Type checking   | `mypy src/`          |

```bash
# Formatear todo
black src/ tests/
isort src/ tests/

# Verificar estilo
flake8 src/ tests/
mypy src/

# Todo junto (usando Makefile)
make lint
```

### Configuración en pyproject.toml

```toml
[tool.black]
line-length = 120
target-version = ["py311", "py312"]

[tool.isort]
profile = "black"
line_length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

### TypeScript (Frontend)

```bash
cd ui
npm run lint
```

---

## Arquitectura Interna

### Capas de la Aplicación

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                         │
│ - Endpoints REST                                               │
│ - Middlewares (auth, rate limit, security headers)             │
│ - Request/Response models (Pydantic)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Application Layer                              │
│ - RAGService (orquestación)                                    │
│ - PromptBuilder, Chunking, Reranking                           │
│ - DLP/PII enforcement                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Domain Layer                                 │
│ - Value Objects: DocumentChunk, Answer, RetrievalResult        │
│ - Ports (interfaces): RetrieverPort, LLMPort, CachePort        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                            │
│ - Adapters: QdrantRetriever, HFLLM, RedisCache                 │
│ - External services: PostgreSQL, Qdrant, Redis, HF API         │
└─────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

1. **Request** llega a FastAPI
2. **Middleware** valida auth, rate limit
3. **Endpoint** delega a `RAGService`
4. **RAGService** usa `RetrieverPort` (implementado por `QdrantRetriever`)
5. **Re-ranking** y selección de chunks
6. **PromptBuilder** construye prompt
7. **LLMPort** (implementado por `HFLLM`) genera respuesta
8. **DLP** aplica redacción de PII
9. **Response** retornada al cliente

### Añadir un Nuevo LLM Provider

```python
# src/cortex_ka/infrastructure/llm_openai.py

from ..domain.ports import LLMPort

class OpenAILLM(LLMPort):
    """OpenAI GPT provider."""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self._client = openai.OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    def generate_stream(self, prompt: str) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

Luego modificar `_select_llm()` en `api/main.py`:

```python
def _select_llm():
    provider = settings.llm_provider.lower()
    if provider == "hf":
        return HFLLM(...)
    elif provider == "openai":
        return OpenAILLM(api_key=settings.openai_api_key)
    return _FakeLLM()
```

### Añadir un Nuevo Endpoint

```python
# En src/cortex_ka/api/main.py

from pydantic import BaseModel

class NewFeatureRequest(BaseModel):
    param1: str
    param2: int = 10

class NewFeatureResponse(BaseModel):
    result: str
    metadata: dict

@app.post("/api/new-feature", response_model=NewFeatureResponse)
def new_feature(
    payload: NewFeatureRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Descripción del nuevo endpoint.

    Solo accesible para usuarios autenticados.
    """
    # Verificar permisos si es necesario
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(403, "Forbidden")

    # Lógica del endpoint
    result = process_new_feature(payload.param1, payload.param2)

    # Auditar si es operación sensible
    _audit(login_db_session, operation="new_feature", outcome="success")

    return NewFeatureResponse(result=result, metadata={})
```

---

## Flujo de Contribución

### 1. Fork y Clone

```bash
# Fork en GitHub, luego:
git clone https://github.com/TU_USUARIO/cortex-knowledge-assistant.git
cd cortex-knowledge-assistant
git remote add upstream https://github.com/DeepRatAI/cortex-knowledge-assistant.git
```

### 2. Crear Branch

```bash
git checkout -b feature/mi-nueva-funcionalidad
```

**Convención de nombres**:

- `feature/descripcion` - Nueva funcionalidad
- `fix/descripcion` - Bug fix
- `docs/descripcion` - Documentación
- `refactor/descripcion` - Refactoring

### 3. Desarrollar

```bash
# Hacer cambios...
# Ejecutar tests
pytest tests/ -v

# Verificar estilo
make lint
```

### 4. Commit

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git add .
git commit -m "feat: añadir soporte para OpenAI GPT-4"
# o
git commit -m "fix: corregir rate limiting para endpoints streaming"
# o
git commit -m "docs: actualizar guía de despliegue"
```

### 5. Push y PR

```bash
git push origin feature/mi-nueva-funcionalidad
# Crear Pull Request en GitHub
```

### Checklist de PR

- [ ] Tests pasan localmente
- [ ] Coverage no disminuye significativamente
- [ ] Código sigue estilo del proyecto
- [ ] Documentación actualizada si aplica
- [ ] CHANGELOG.md actualizado
- [ ] Sin secrets o datos sensibles

---

## Documentación

### Docstrings

Usamos formato Google:

```python
def calculate_score(chunk: DocumentChunk, query: str) -> float:
    """Calculate relevance score for a chunk.

    Combines semantic similarity with keyword matching
    using a weighted average.

    Args:
        chunk: The document chunk to score.
        query: The user's search query.

    Returns:
        Relevance score between 0 and 1.

    Raises:
        ValueError: If chunk or query is empty.

    Example:
        >>> score = calculate_score(chunk, "requisitos cuenta")
        >>> print(f"Score: {score:.2f}")
        Score: 0.85
    """
```

### Actualizar Documentación

```bash
# Documentación está en docs/
# Formato: Markdown

# Para preview local (si usas Docusaurus):
cd docs
npm run start
```

---

## Debugging

### Logs Detallados

```bash
export CKA_LOG_LEVEL=DEBUG
uvicorn src.cortex_ka.api.main:app --reload
```

### Debugger (VS Code)

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Cortex API",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["src.cortex_ka.api.main:app", "--reload"],
      "env": {
        "CKA_LLM_PROVIDER": "Fake",
        "DATABASE_URL": "sqlite:///./dev.db"
      }
    },
    {
      "name": "Tests",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v", "-s"]
    }
  ]
}
```

### Profiling

```python
# Para profiling de performance
import cProfile
import pstats

with cProfile.Profile() as pr:
    result = rag_service.answer("mi query")

stats = pstats.Stats(pr)
stats.sort_stats("cumulative")
stats.print_stats(20)
```

---

## Versionado

Seguimos [Semantic Versioning](https://semver.org/):

- **MAJOR**: Cambios incompatibles en API
- **MINOR**: Nueva funcionalidad retrocompatible
- **PATCH**: Bug fixes retrocompatibles

### Crear Release

```bash
# 1. Actualizar versión en pyproject.toml
# 2. Actualizar CHANGELOG.md
# 3. Commit
git commit -am "chore: release v1.1.0"

# 4. Tag
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0

# 5. GitHub Actions construye y publica
```

---

## Recursos

### Documentación de Dependencias

- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Qdrant](https://qdrant.tech/documentation/)
- [sentence-transformers](https://www.sbert.net/)

### Papers de Referencia

- [RAG: Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401)
- [DPR: Dense Passage Retrieval](https://arxiv.org/abs/2004.04906)
- [ColBERT: Efficient Passage Retrieval](https://arxiv.org/abs/2004.12832)

---

## FAQ de Desarrollo

### ¿Por qué Arquitectura Hexagonal?

- **Testabilidad**: Cada componente puede testearse aisladamente
- **Flexibilidad**: Cambiar LLM provider sin tocar lógica de negocio
- **Claridad**: Separación clara de responsabilidades

### ¿Por qué SQLite en desarrollo?

- **Simplicidad**: No requiere servidor adicional
- **Portabilidad**: El archivo `.db` es autocontenido
- **Compatibilidad**: El código es igual que con PostgreSQL gracias a SQLAlchemy

### ¿Cómo añado un nuevo tipo de PII?

1. Añadir regex en `application/pii.py`
2. Actualizar `classify_pii()` en `pii_classifier.py`
3. Añadir test en `tests/test_pii_classifier.py`
4. Actualizar documentación de seguridad

---

<p align="center">
  <a href="deployment.md">← Despliegue</a> •
  <a href="index.md">Índice →</a>
</p>
