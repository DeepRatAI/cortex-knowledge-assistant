# Arquitectura

Este documento describe la arquitectura técnica de Cortex Knowledge Assistant, incluyendo el diseño del sistema, componentes principales y flujo de datos.

---

## Principios de Diseño

Cortex sigue los principios de **Arquitectura Hexagonal** (Ports & Adapters):

1. **Dominio Aislado**: La lógica de negocio no depende de frameworks externos
2. **Inversión de Dependencias**: Los componentes de infraestructura implementan interfaces (ports)
3. **Testabilidad**: Cada componente puede ser probado de forma aislada
4. **Extensibilidad**: Nuevos adaptadores (LLMs, retrievers, caches) sin modificar el núcleo

---

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   React UI      │    │   FastAPI       │    │   Prometheus    │         │
│  │   (TypeScript)  │───▶│   REST API      │◀───│   /metrics      │         │
│  └─────────────────┘    └────────┬────────┘    └─────────────────┘         │
│                                  │                                           │
│  Endpoints: /query, /auth/login, /subjects, /admin/*, /health              │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                          APPLICATION LAYER                                    │
├──────────────────────────────────┼───────────────────────────────────────────┤
│                                  ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                         RAGService                               │        │
│  │ - Query expansion & normalization                               │        │
│  │ - Multi-stage retrieval (semantic + keyword)                    │        │
│  │ - Hybrid scoring & re-ranking                                   │        │
│  │ - Context assembly & prompt building                            │        │
│  │ - PII sensitivity tracking                                      │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                  │                                           │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │  DLP/PII       │  │ PromptBuilder  │  │   Chunking     │                 │
│  │  Enforcement   │  │ (RAG context)  │  │   (Semantic)   │                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                            DOMAIN LAYER                                       │
├──────────────────────────────────┼───────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │ DocumentChunk  │  │ RetrievalResult│  │    Answer      │                 │
│  │ (Value Object) │  │ (Value Object) │  │ (Value Object) │                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                          PORTS (Interfaces)                     │         │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────┐│         │
│  │  │ RetrieverPort│ │  LLMPort     │ │ EmbedderPort │ │CachePort││         │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────┘│         │
│  └────────────────────────────────────────────────────────────────┘         │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                        INFRASTRUCTURE LAYER                                   │
├──────────────────────────────────┼───────────────────────────────────────────┤
│                                  ▼                                           │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │ QdrantRetriever│  │    HFLLM       │  │  LocalEmbedder │                 │
│  │ (Vector Search)│  │ (HuggingFace)  │  │ (Sentence-TF)  │                 │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                 │
│          │                   │                   │                           │
│  ┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐                 │
│  │     Qdrant     │  │   HuggingFace  │  │ sentence-      │                 │
│  │   (External)   │  │  Inference API │  │ transformers   │                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │   RedisCache   │  │ PostgreSQL     │  │ ConversationMem│                 │
│  │ (Rate Limit)   │  │ (Users, Audit) │  │ (In-Memory)    │                 │
│  └───────┬────────┘  └───────┬────────┘  └────────────────┘                 │
│          │                   │                                               │
│  ┌───────▼────────┐  ┌───────▼────────┐                                     │
│  │     Redis      │  │   PostgreSQL   │                                     │
│  │   (External)   │  │   (External)   │                                     │
│  └────────────────┘  └────────────────┘                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Estructura del Código

```
src/cortex_ka/
├── api/                     # Presentation Layer
│   └── main.py              # FastAPI app, endpoints, middlewares
│
├── application/             # Application Layer (Use Cases)
│   ├── rag_service.py       # Orquestación RAG principal
│   ├── chunking.py          # Chunking semántico de documentos
│   ├── prompt_builder.py    # Construcción de prompts para LLM
│   ├── query_processing.py  # Normalización y expansión de queries
│   ├── reranking.py         # Re-ranking híbrido de resultados
│   ├── pii_classifier.py    # Clasificación de sensibilidad PII
│   ├── pii_masking.py       # Enmascaramiento PII por rol para contexto LLM
│   ├── pii.py               # Redacción de PII
│   ├── dlp.py               # Facade de Data Loss Prevention
│   └── metrics.py           # Métricas Prometheus
│
├── domain/                  # Domain Layer (Core Business)
│   ├── models.py            # Value Objects: DocumentChunk, Answer
│   └── ports.py             # Interfaces: RetrieverPort, LLMPort, etc.
│
├── infrastructure/          # Infrastructure Layer (Adapters)
│   ├── retriever_qdrant.py  # Implementación Qdrant
│   ├── retriever_stub.py    # Stub para tests
│   ├── llm_hf.py            # HuggingFace Inference API
│   ├── llm_ollama.py        # Ollama (local)
│   ├── embedding_local.py   # sentence-transformers
│   ├── redis_cache.py       # Cache con Redis
│   ├── memory_cache.py      # Cache in-memory
│   └── memory_store.py      # Conversación y rate limiting
│
├── auth/                    # Authentication & Authorization
│   ├── models.py            # User, Subject, UserSubject (SQLAlchemy)
│   ├── db.py                # Session factory, inicialización
│   ├── jwt_utils.py         # JWT creation/validation
│   └── passwords.py         # Hashing con bcrypt
│
├── transactions/            # Transactional Domain (Banking Demo)
│   ├── models.py            # ServiceInstance, ServiceTransaction
│   ├── service.py           # BankingDomainService
│   └── seed_demo.py         # Generación de datos demo
│
├── system/                  # System Administration
│   ├── setup.py             # First-run wizard, user management
│   ├── status.py            # Health checks, system status
│   └── data_admin.py        # Subject data CRUD with audit
│
├── scripts/                 # Ingestion & Maintenance
│   ├── ingest_pdfs.py       # PDF text extraction
│   ├── ingest_docs.py       # Document upsert to Qdrant
│   └── init_qdrant.py       # Collection initialization
│
├── demos/                   # Demo Mode Support
│   ├── scheduler.py         # Auto-reset scheduler
│   └── seed_university.py   # University domain demo data
│
├── config.py                # Pydantic Settings (env vars)
├── logging.py               # Structured logging (structlog)
└── build_info.py            # Version, git SHA, build time
```

---

## Flujo de una Consulta RAG

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUJO DE CONSULTA                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Usuario: "¿Cuáles son los requisitos para abrir una cuenta?"
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 1. AUTENTICACIÓN                          │
│   - Validar JWT token                    │
│   - Extraer user_id, subject_ids, role   │
│   - Verificar permisos multi-tenant      │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 2. RATE LIMITING                          │
│   - Verificar límite por usuario/key     │
│   - Retornar 429 si excedido            │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 3. QUERY PROCESSING                       │
│   - Normalizar texto                     │
│   - Extraer keywords                     │
│   - Detectar menciones a documentos      │
│   - Generar variantes de búsqueda        │
│   - Enriquecer con historial (memoria)   │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 4. RETRIEVAL (Multi-Stage)                │
│   - Generar embedding de la query        │
│   - Búsqueda en Qdrant (top-k=80)        │
│   - Filtrar por subject_id (multi-tenant)│
│   - Filtrar por context_type si aplica   │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 5. RE-RANKING HÍBRIDO                     │
│   - Score semántico (50%)                │
│   - Score keyword (15%)                  │
│   - Boost por documento mencionado (25%) │
│   - Boost por topic relevante (10%)      │
│   - Deduplicación (Jaccard > 0.85)       │
│   - Límite por documento (max 6 chunks)  │
│   - Selección final (15 chunks)          │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 6. CONTEXT ENRICHMENT                     │
│   - Obtener snapshot transaccional       │
│      (productos, movimientos del cliente) │
│   - Incluir en contexto si disponible    │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 7. PROMPT BUILDING                        │
│   - Construir prompt con:                │
│      · System instructions                │
│      · Chunks recuperados                 │
│      · Snapshot transaccional             │
│      · Query del usuario                  │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 8. LLM GENERATION                         │
│   - Enviar prompt a HuggingFace API      │
│   - Recibir respuesta generada           │
│   - Tracking de PII sensitivity          │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 9. DLP ENFORCEMENT                        │
│   - Aplicar redacción de PII             │
│   - Respetar dlp_level del usuario       │
│   - Usuarios "privileged" ven todo       │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ 10. RESPONSE                              │
│   - Guardar en memoria de conversación   │
│   - Registrar en audit log               │
│   - Emitir métricas Prometheus           │
│   - Retornar answer + citations          │
└──────────────────────────────────────────┘
                    │
                    ▼
{
  "answer": "Para abrir una cuenta necesita...",
  "used_chunks": ["chunk-1", "chunk-2"],
  "citations": [{"id": "chunk-1", "source": "requisitos.pdf"}],
  "session_id": "user-session-123"
}
```

---

## Modelo de Datos

### Entities (SQLAlchemy ORM)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            IDENTITY & AUTH                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐
│       User         │       │    UserSubject     │       │      Subject       │
├────────────────────┤       ├────────────────────┤       ├────────────────────┤
│ id: int (PK)       │──┐    │ id: int (PK)       │    ┌──│ id: int (PK)       │
│ username: str      │  │    │ user_id: int (FK)  │────┘  │ subject_key: str   │
│ password_hash: str │  └───▶│ subject_id: str    │       │ subject_type: str  │
│ user_type: str     │       │ created_at: dt     │       │ display_name: str  │
│ role: str          │       └────────────────────┘       │ status: str        │
│ dlp_level: str     │                                    │ full_name: str     │
│ status: str        │                                    │ document_id: str   │
│ can_access_all: bool                                    │ tax_id: str        │
│ created_at: dt     │                                    │ email: str         │
│ updated_at: dt     │                                    │ phone: str         │
└────────────────────┘                                    │ attributes: JSON   │
                                                          │ created_at: dt     │
                                                          │ updated_at: dt     │
                                                          └─────────┬──────────┘
                                                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRANSACTIONAL DOMAIN                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                                                    │
                                                          ┌─────────▼──────────┐
                                                          │  ServiceInstance   │
                                                          ├────────────────────┤
                                                          │ id: int (PK)       │
                                                          │ subject_id: int(FK)│
                                                          │ service_type: str  │
                                                          │ service_key: str   │
                                                          │ status: str        │
                                                          │ opened_at: dt      │
                                                          │ closed_at: dt      │
                                                          │ extra_metadata:JSON│
                                                          └─────────┬──────────┘
                                                                    │
                                                          ┌─────────▼──────────┐
                                                          │ServiceTransaction  │
                                                          ├────────────────────┤
                                                          │ id: int (PK)       │
                                                          │ service_inst_id:FK │
                                                          │ timestamp: dt      │
                                                          │ transaction_type   │
                                                          │ amount: float      │
                                                          │ currency: str      │
                                                          │ description: str   │
                                                          │ extra_metadata:JSON│
                                                          └────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              AUDIT LOG                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────────┐
│      AuditLog      │
├────────────────────┤
│ id: int (PK)       │
│ user_id: str       │
│ username: str      │
│ subject_key: str   │
│ operation: str     │  (login, query, admin_*, etc.)
│ outcome: str       │  (success, failure, denied)
│ details: JSON      │
│ created_at: dt     │
└────────────────────┘
```

### Value Objects (Pydantic)

```python
# domain/models.py

class DocumentChunk:
    id: str                    # UUID del chunk
    text: str                  # Contenido textual
    source: str                # Documento origen
    doc_id: str | None         # ID del documento padre
    filename: str | None       # Nombre del archivo
    score: float | None        # Score de similaridad
    pii_sensitivity: str | None  # "none", "low", "medium", "high"

class RetrievalResult:
    query: str
    chunks: list[DocumentChunk]

class Answer:
    answer: str
    query: str
    used_chunks: list[str]     # IDs de chunks usados
    citations: list[dict]      # [{id, source}]
    max_pii_sensitivity: str | None
```

---

## Puertos e Interfaces

Los "puertos" definen contratos que los adaptadores deben implementar:

```python
# domain/ports.py

class RetrieverPort(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        k: int = 5,
        subject_id: str | None = None,
        context_type: str | None = None,
    ) -> RetrievalResult:
        """Búsqueda semántica con filtros multi-tenant."""

class LLMPort(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generar respuesta a partir de prompt."""

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Streaming de tokens (opcional)."""

class EmbedderPort(ABC):
    @abstractmethod
    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        """Generar embeddings para textos."""

class CachePort(ABC):
    @abstractmethod
    def get_answer(self, query: str) -> str | None: ...
    @abstractmethod
    def set_answer(self, query: str, answer: str) -> None: ...
```

---

## Multi-Tenancy

El sistema soporta múltiples "tenants" (clientes, organizaciones) con aislamiento de datos:

### Reglas de Acceso

| Tipo Usuario | can_access_all | Comportamiento                  |
| ------------ | -------------- | ------------------------------- |
| `customer`   | `false`        | Solo ve sus propios subject_ids |
| `employee`   | `false`        | Solo ve subject_ids asignados   |
| `employee`   | `true`         | Puede ver cualquier subject     |
| `admin`      | `true`         | Acceso total + endpoints admin  |

### Flujo de Autorización

```python
# Simplificado de api/main.py

if user_type == "employee" and can_access_all:
    # Admin puede consultar cualquier cliente
    subject_id = requested_subject  # O None para docs públicos
elif user_type == "employee":
    # Empleado restringido a sus asignados
    if requested_subject in allowed_subject_ids:
        subject_id = requested_subject
    else:
        subject_id = allowed_subject_ids[0]
else:
    # Customer: siempre usa su propio subject
    subject_id = allowed_subject_ids[0]
```

---

## Observabilidad

### Métricas (Prometheus)

```
# Latencia de queries
cortex_query_latency_seconds{quantile="0.5"}
cortex_query_latency_seconds{quantile="0.95"}

# Chunks recuperados
cortex_retrieved_chunks{quantile="0.5"}

# Requests HTTP
cortex_http_requests_total{endpoint="/query", status_class="2xx"}
cortex_http_request_latency_seconds{endpoint="/query"}

# Info del modelo activo
cortex_active_model_info{provider="hf", model="meta-llama/..."}
```

### Logging Estructurado

```json
{
  "event": "query_answered",
  "request_id": "abc123",
  "user_id": "user-1",
  "subject_id": "CLI-81093",
  "duration_sec": 1.23,
  "chunks_used": 5
}
```

### Tracing (OpenTelemetry)

Habilitado con `CKA_ENABLE_TRACING=true`. Exporta spans a cualquier collector OTLP.

---

## Dependencias Externas

| Servicio            | Propósito               | Failover                 |
| ------------------- | ----------------------- | ------------------------ |
| **Qdrant**          | Vector search           | Stub retriever en tests  |
| **PostgreSQL**      | Usuarios, transacciones | Requerido                |
| **Redis**           | Cache, rate limiting    | In-memory fallback       |
| **HuggingFace API** | LLM generation          | Fake LLM para desarrollo |

---

<p align="center">
  <a href="getting-started.md">← Inicio Rápido</a> •
  <a href="api-reference.md">API Reference →</a>
</p>
