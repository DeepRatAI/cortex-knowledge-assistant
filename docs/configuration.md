# Configuración

Guía completa de todas las variables de entorno y opciones de configuración de Cortex Knowledge Assistant.

---

## Resumen de Variables

Todas las variables usan el prefijo `CKA_` (Cortex Knowledge Assistant).

| Categoría                         | Variables                                                |
| --------------------------------- | -------------------------------------------------------- |
| [LLM](#llm-large-language-model)  | `CKA_LLM_PROVIDER`, `HF_API_KEY`, `CKA_HF_MODEL`         |
| [Qdrant](#qdrant-vector-database) | `CKA_QDRANT_URL`, `CKA_QDRANT_API_KEY`, `CKA_USE_QDRANT` |
| [Redis](#redis-cache)             | `CKA_REDIS_HOST`, `CKA_REDIS_PORT`, `CKA_USE_REDIS`      |
| [Database](#database)             | `DATABASE_URL`                                           |
| [Security](#security)             | `JWT_SECRET_KEY`, `CKA_API_KEY`, `CKA_HTTPS_ENABLED`     |
| [Rate Limiting](#rate-limiting)   | `CKA_RATE_LIMIT_QPM`, `CKA_RATE_LIMIT_BURST`             |
| [RAG](#rag-pipeline)              | `CKA_MAX_INPUT_TOKENS`, `CKA_MAX_OUTPUT_TOKENS`          |
| [Observability](#observability)   | `CKA_LOG_LEVEL`, `CKA_ENABLE_TRACING`                    |
| [Demo Mode](#demo-mode)           | `CKA_DEMO_DOMAIN`, `CKA_DEMO_RESET_INTERVAL`             |

---

## LLM (Large Language Model)

### CKA_LLM_PROVIDER

Proveedor de LLM a utilizar.

| Valor  | Descripción                                             |
| ------ | ------------------------------------------------------- |
| `HF`   | HuggingFace Inference API (recomendado para producción) |
| `Fake` | LLM simulado para desarrollo/tests                      |

**Default**: `Fake`

```env
CKA_LLM_PROVIDER=HF
```

### HF_API_KEY

API Key de HuggingFace para acceso a modelos.

- Obtener en: https://huggingface.co/settings/tokens
- **Requerido** si `CKA_LLM_PROVIDER=HF`

```env
HF_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### CKA_HF_MODEL

Modelo de HuggingFace a utilizar.

**Default**: Selección automática del mejor modelo disponible (prioriza instruct/chat)

```env
CKA_HF_MODEL=meta-llama/Llama-3.1-8B-Instruct
```

**Modelos Recomendados**:

- `meta-llama/Llama-3.1-8B-Instruct` - Excelente calidad
- `mistralai/Mistral-7B-Instruct-v0.3` - Rápido y capaz
- `Qwen/Qwen2.5-7B-Instruct` - Buen soporte multilingüe

### CKA_HF_WAIT_FOR_MODEL

Esperar a que el modelo esté listo (útil para modelos con cold start).

**Default**: `true`

```env
CKA_HF_WAIT_FOR_MODEL=true
```

### CKA_MAX_OUTPUT_TOKENS

Máximo de tokens en la respuesta del LLM.

**Default**: `512`

```env
CKA_MAX_OUTPUT_TOKENS=8192
```

### CKA_TEMPERATURE

Temperatura del LLM (creatividad vs determinismo).

**Default**: `0.3`

```env
CKA_TEMPERATURE=0.3
```

---

## Qdrant (Vector Database)

### CKA_USE_QDRANT

Habilitar búsqueda vectorial con Qdrant.

**Default**: `false` (usa StubRetriever para tests)

```env
CKA_USE_QDRANT=true
```

### CKA_QDRANT_URL

URL del servidor Qdrant.

**Default**: `http://localhost:6333`

```env
CKA_QDRANT_URL=http://qdrant:6333
```

### CKA_QDRANT_API_KEY

API Key para Qdrant (si está configurado con autenticación).

**Default**: vacío (sin autenticación)

```env
CKA_QDRANT_API_KEY=your-qdrant-api-key
```

### CKA_QDRANT_COLLECTION_DOCS

Nombre de la colección de documentos.

**Default**: `corporate_docs`

```env
CKA_QDRANT_COLLECTION_DOCS=corporate_docs
```

### CKA_QDRANT_TOP_K

Número máximo de resultados iniciales de Qdrant.

**Default**: `5`

```env
CKA_QDRANT_TOP_K=80
```

---

## Redis (Cache)

### CKA_USE_REDIS

Habilitar cache con Redis.

**Default**: `false` (usa InMemoryCache)

```env
CKA_USE_REDIS=true
```

### CKA_REDIS_HOST

Host del servidor Redis.

**Default**: `redis`

```env
CKA_REDIS_HOST=redis
```

### CKA_REDIS_PORT

Puerto de Redis.

**Default**: `6379`

```env
CKA_REDIS_PORT=6379
```

### REDIS_URL

URL completa de Redis (alternativa a HOST/PORT).

```env
REDIS_URL=redis://redis:6379/0
```

---

## Database

### DATABASE_URL

URL de conexión a PostgreSQL.

**Formato**: `postgresql+psycopg://user:password@host:port/database`

```env
DATABASE_URL=postgresql+psycopg://cortex:secure_password@postgres:5432/cortex
```

**Para desarrollo con SQLite**:

```env
DATABASE_URL=sqlite:///./cortex.db
```

### POSTGRES_PASSWORD

Password de PostgreSQL (usado por docker-compose).

**Default**: `cortex_change_me`

```env
POSTGRES_PASSWORD=your_secure_password
```

---

## Security

### JWT_SECRET_KEY

Clave secreta para firmar tokens JWT.

- **Mínimo**: 32 caracteres
- **Recomendado**: 64 caracteres aleatorios

```env
JWT_SECRET_KEY=your-super-secret-key-at-least-32-characters-long
```

**Generar clave segura**:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### CKA_API_KEY

API Key para autenticación legacy (desarrollo).

> **Nota**: En producción, usar exclusivamente JWT.

```env
CKA_API_KEY=development-only-api-key
```

### CKA_ENABLE_DEMO_API_KEY

Habilitar autenticación por API key legacy.

**Default**: `true`

```env
CKA_ENABLE_DEMO_API_KEY=false  # Deshabilitar en producción
```

### CKA_HTTPS_ENABLED

Habilitar headers de seguridad para HTTPS.

**Default**: `false`

```env
CKA_HTTPS_ENABLED=true
```

**Headers habilitados**:

- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy` (CSP)

### CKA_CSP_POLICY

Política de Content Security Policy.

**Default**:

```
default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'
```

```env
CKA_CSP_POLICY=default-src 'self'; script-src 'self' 'unsafe-inline'
```

### CKA_DLP_ENABLED

Habilitar Data Loss Prevention (redacción de PII).

**Default**: `true`

```env
CKA_DLP_ENABLED=true
```

### CKA_CONFIDENTIAL_RETRIEVAL_ONLY

Modo estricto: prohibir LLM Fake y requerir proveedor real.

**Default**: `false`

```env
CKA_CONFIDENTIAL_RETRIEVAL_ONLY=true
```

---

## Rate Limiting

### CKA_RATE_LIMIT_QPM

Queries por minuto permitidas por usuario.

**Default**: `120`

```env
CKA_RATE_LIMIT_QPM=60
```

### CKA_RATE_LIMIT_BURST

Capacidad de burst adicional.

**Default**: `0`

```env
CKA_RATE_LIMIT_BURST=10
```

### CKA_RATE_LIMIT_WINDOW_SECONDS

Ventana de tiempo para rate limiting.

**Default**: `60`

```env
CKA_RATE_LIMIT_WINDOW_SECONDS=60
```

---

## RAG Pipeline

### CKA_MAX_INPUT_TOKENS

Máximo de tokens de entrada por request.

**Default**: `2048`

```env
CKA_MAX_INPUT_TOKENS=4096
```

### CKA_CONVERSATION_MAX_TURNS

Máximo de turnos de conversación a incluir en contexto.

**Default**: `5`

```env
CKA_CONVERSATION_MAX_TURNS=10
```

### CKA_EMBEDDING_MODEL

Modelo de embeddings para vectorización.

**Default**: `sentence-transformers/all-MiniLM-L6-v2`

```env
CKA_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

## CORS

### CKA_CORS_ORIGINS

Orígenes permitidos para CORS (separados por coma).

**Default**: `*`

```env
CKA_CORS_ORIGINS=http://localhost:3000,https://cortex.deeprat.tech
```

---

## Observability

### CKA_LOG_LEVEL

Nivel de logging.

| Valor     | Descripción                 |
| --------- | --------------------------- |
| `DEBUG`   | Todo, incluyendo debug      |
| `INFO`    | Información operacional     |
| `WARNING` | Solo advertencias y errores |
| `ERROR`   | Solo errores                |

**Default**: `INFO`

```env
CKA_LOG_LEVEL=DEBUG
```

### CKA_ENABLE_TRACING

Habilitar tracing con OpenTelemetry.

**Default**: `false`

```env
CKA_ENABLE_TRACING=true
```

Requiere configurar endpoint OTLP:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
```

---

## Streaming

### CKA_ENABLE_STREAMING

Habilitar endpoint `/chat/stream`.

**Default**: `false`

```env
CKA_ENABLE_STREAMING=true
```

---

## Demo Mode

### CKA_DEMO_DOMAIN

Dominio de la demo (afecta labels y datos).

| Valor        | Descripción                              |
| ------------ | ---------------------------------------- |
| `banking`    | Demo bancaria (productos, transacciones) |
| `university` | Demo universitaria (materias, notas)     |
| `clinic`     | Demo clínica                             |

**Default**: `banking`

```env
CKA_DEMO_DOMAIN=university
```

### CKA_DEMO_RESET_ENABLED

Habilitar reset automático de datos demo.

**Default**: `false`

```env
CKA_DEMO_RESET_ENABLED=true
```

### CKA_DEMO_RESET_INTERVAL_HOURS

Intervalo en horas entre resets automáticos.

**Default**: `1`

```env
CKA_DEMO_RESET_INTERVAL_HOURS=2
```

---

## Frontend (UI)

Variables para la UI de React (prefijo `VITE_`):

### VITE_DEMO_DOMAIN

Dominio de la demo para la UI.

```env
VITE_DEMO_DOMAIN=banking
```

### VITE_DEMO_MODE

Modo de demo de la UI.

| Valor          | Descripción            |
| -------------- | ---------------------- |
| `none`         | Sin modo demo          |
| `fce_iuc`      | Demo FCE-IUC           |
| `firstrun`     | Wizard de primer uso   |
| `banking_demo` | Demo bancaria completa |

```env
VITE_DEMO_MODE=none
```

### VITE_DEMO_RESET_ENABLED

Mostrar countdown de reset en la UI.

```env
VITE_DEMO_RESET_ENABLED=true
```

---

## Data Directory

### CKA_DATA_DIR

Directorio base para datos de la aplicación.

**Default**: `/app/data`

```env
CKA_DATA_DIR=/app/data
```

**Estructura**:

```
/app/data/
├── documentacion/
│   ├── publica/       # PDFs públicos
│   └── educativa/     # Material educativo
└── logs/              # Logs de aplicación
```

---

## Archivo .env de Ejemplo

```env
# ══════════════════════════════════════════════════════════════════════════════
# Cortex Knowledge Assistant - Production Configuration
# ══════════════════════════════════════════════════════════════════════════════

# === LLM Configuration ===
CKA_LLM_PROVIDER=HF
HF_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CKA_HF_MODEL=meta-llama/Llama-3.1-8B-Instruct
CKA_MAX_OUTPUT_TOKENS=8192
CKA_TEMPERATURE=0.3

# === Vector Database (Qdrant) ===
CKA_USE_QDRANT=true
CKA_QDRANT_URL=http://qdrant:6333
CKA_QDRANT_COLLECTION_DOCS=corporate_docs

# === Cache (Redis) ===
CKA_USE_REDIS=true
CKA_REDIS_HOST=redis
CKA_REDIS_PORT=6379

# === Database (PostgreSQL) ===
DATABASE_URL=postgresql+psycopg://cortex:${POSTGRES_PASSWORD}@postgres:5432/cortex
POSTGRES_PASSWORD=your_secure_password_here

# === Security ===
JWT_SECRET_KEY=your-super-secret-key-at-least-32-characters-long-or-longer
CKA_HTTPS_ENABLED=true
CKA_DLP_ENABLED=true
CKA_ENABLE_DEMO_API_KEY=false

# === Rate Limiting ===
CKA_RATE_LIMIT_QPM=60
CKA_RATE_LIMIT_BURST=10

# === CORS ===
CKA_CORS_ORIGINS=https://cortex.example.com

# === Observability ===
CKA_LOG_LEVEL=INFO
CKA_ENABLE_TRACING=false

# === Streaming ===
CKA_ENABLE_STREAMING=true
```

---

## Validación de Configuración

El sistema valida la configuración al iniciar. Errores comunes:

### Error: "HF_API_KEY missing"

```
RuntimeError: HF_API_KEY missing
```

**Solución**: Configurar `HF_API_KEY` o cambiar `CKA_LLM_PROVIDER=Fake`

### Error: "confidential_retrieval_only is enabled but llm_provider is 'Fake'"

```
RuntimeError: confidential_retrieval_only is enabled but llm_provider is 'Fake'
```

**Solución**: Configurar un LLM real o deshabilitar `CKA_CONFIDENTIAL_RETRIEVAL_ONLY`

### Warning: "startup_qdrant_collection_init_failed"

Qdrant no está disponible o la colección no existe.

**Solución**: Verificar que Qdrant está corriendo e inicializar la colección

---

## Variables en Docker Compose

Las variables se pasan a los contenedores a través de:

1. **Archivo `.env`** (recomendado):

   ```yaml
   env_file:
    - .env
   ```

2. **Environment directo**:

   ```yaml
   environment:
    - CKA_QDRANT_URL=http://qdrant:6333
   ```

3. **Build args** (para UI):
   ```yaml
   build:
     args:
       VITE_DEMO_DOMAIN: ${VITE_DEMO_DOMAIN:-banking}
   ```

---

<p align="center">
  <a href="api-reference.md">← API Reference</a> •
  <a href="security.md">Seguridad →</a>
</p>
