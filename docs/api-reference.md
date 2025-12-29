# API Reference

Referencia completa de la API REST de Cortex Knowledge Assistant.

**Base URL**: `http://localhost:8088` (desarrollo) | `https://api.cortex.deeprat.tech` (demo)

---

## Autenticación

Cortex utiliza **JWT Bearer tokens** para autenticación. Todos los endpoints (excepto `/health`, `/live`, `/ready`, `/auth/login`) requieren autenticación.

### Obtener Token

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your_password"
}
```

**Respuesta** (200 OK):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "1",
    "username": "admin",
    "user_type": "employee",
    "role": "admin",
    "dlp_level": "standard",
    "can_access_all_subjects": true,
    "subject_ids": []
  }
}
```

### Usar Token

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## Endpoints por Categoría

- [Health & Status](#health--status)
- [Authentication](#authentication)
- [RAG Queries](#rag-queries)
- [Subjects (Clientes)](#subjects)
- [Transactional Data](#transactional-data)
- [Admin - Users](#admin---users)
- [Admin - Documents](#admin---documents)
- [Admin - Products & Transactions](#admin---products--transactions)
- [System Setup](#system-setup)
- [Metrics](#metrics)

---

## Health & Status

### GET /health

Estado completo del sistema con todos los componentes.

**Auth**: No requerida

```bash
curl http://localhost:8088/health
```

**Respuesta** (200 OK):

```json
{
  "status": "healthy",
  "timestamp": "2024-12-27T15:30:00Z",
  "components": {
    "database": { "healthy": true, "status": "connected" },
    "qdrant": { "healthy": true, "status": "connected", "documents": 1234 },
    "redis": { "healthy": true, "status": "connected" },
    "llm": {
      "healthy": true,
      "provider": "hf",
      "model": "meta-llama/Llama-3.1-8B-Instruct"
    }
  }
}
```

### GET /live

Probe de liveness para Kubernetes.

**Auth**: No requerida

```bash
curl http://localhost:8088/live
```

**Respuesta** (200 OK):

```json
{
  "status": "alive",
  "timestamp": "2024-12-27T15:30:00Z"
}
```

### GET /ready

Probe de readiness para Kubernetes.

**Auth**: No requerida

**Respuesta** (200 OK si listo, 503 si no):

```json
{
  "ready": true,
  "timestamp": "2024-12-27T15:30:00Z",
  "checks": {
    "database": true,
    "qdrant": true,
    "llm": true
  }
}
```

### GET /version

Información de versión y build.

**Auth**: No requerida

```json
{
  "git_sha": "abc123def",
  "build_time": "2024-12-27T12:00:00Z",
  "app_version": "0.1.0-beta"
}
```

---

## Authentication

### POST /auth/login

Autenticar usuario y obtener JWT.

**Request**:

```json
{
  "username": "string",
  "password": "string"
}
```

**Respuesta** (200 OK): Ver [Obtener Token](#obtener-token)

**Errores**:

- `401`: Credenciales inválidas
- `403`: Usuario deshabilitado

### POST /login

Alias de `/auth/login` para compatibilidad.

---

## RAG Queries

### POST /query

Realizar una consulta RAG con respuesta completa.

**Auth**: Bearer Token requerido

**Request**:

```json
{
  "query": "¿Cuáles son los requisitos para abrir una cuenta?",
  "session_id": "optional-session-id",
  "subject_id": "CLI-81093",
  "context_type": "public_docs"
}
```

| Campo          | Tipo   | Descripción                                              |
| -------------- | ------ | -------------------------------------------------------- |
| `query`        | string | **Requerido**. Pregunta del usuario (máx 2000 chars)     |
| `session_id`   | string | Opcional. ID de sesión para memoria de conversación      |
| `subject_id`   | string | Opcional. ID del cliente para consultas personalizadas   |
| `context_type` | string | Opcional. Filtro: `public_docs`, `educational`, o `null` |

**Respuesta** (200 OK):

```json
{
  "answer": "Para abrir una cuenta necesita presentar...",
  "used_chunks": ["chunk-id-1", "chunk-id-2", "chunk-id-3"],
  "session_id": "my-session-123",
  "citations": [
    { "id": "chunk-id-1", "source": "requisitos_cuenta.pdf" },
    { "id": "chunk-id-2", "source": "documentacion_general.pdf" }
  ]
}
```

**Errores**:

- `401`: No autenticado
- `403`: Sin permisos para el subject
- `413`: Query demasiado larga
- `422`: Query vacía
- `429`: Rate limited (incluye header `Retry-After`)

### POST /query/stream

Consulta RAG con respuesta en streaming (SSE).

**Auth**: Bearer Token requerido

**Request**: Igual que `/query`

**Respuesta**: `text/event-stream`

```
data: {"token": "Para"}

data: {"token": " abrir"}

data: {"token": " una"}

data: {"token": " cuenta"}

...

data: {"done": true}

```

### GET /chat/stream

Streaming simplificado (requiere `CKA_ENABLE_STREAMING=true`).

**Query Params**: `q` - la consulta

---

## Subjects

### GET /subjects

Listar subjects (clientes/entidades) accesibles para el usuario actual.

**Auth**: Bearer Token requerido

**Respuesta** (200 OK):

```json
[
  {
    "subject_id": "CLI-81093",
    "subject_type": "person",
    "display_name": "Juan García",
    "status": "active"
  },
  {
    "subject_id": "CLI-81094",
    "subject_type": "person",
    "display_name": "María López",
    "status": "active"
  }
]
```

### GET /subjects/{subject_id}

Detalle de un subject específico.

**Auth**: Bearer Token requerido

**Respuesta** (200 OK):

```json
{
  "subject_id": "CLI-81093",
  "subject_type": "person",
  "display_name": "Juan García",
  "status": "active",
  "attributes": {
    "segment": "premium",
    "joined_date": "2020-01-15"
  }
}
```

### GET /subjects/{subject_id}/services

Listar productos/servicios de un subject.

**Auth**: Bearer Token requerido

**Respuesta** (200 OK):

```json
[
  {
    "service_type": "bank_account",
    "service_key": "ES1234567890123456789012",
    "display_name": "Cuenta Corriente",
    "status": "active",
    "metadata": { "currency": "EUR" }
  },
  {
    "service_type": "credit_card",
    "service_key": "****-****-****-1234",
    "display_name": "Visa Gold",
    "status": "active",
    "metadata": { "limit": 5000 }
  }
]
```

---

## Transactional Data

### GET /me/snapshot

Snapshot transaccional del usuario actual (solo customers).

**Auth**: Bearer Token requerido (user_type: customer)

**Respuesta** (200 OK):

```json
{
  "subject_key": "CLI-81093",
  "products": [
    {
      "service_type": "bank_account",
      "service_key": "ES1234567890123456789012",
      "status": "active",
      "extra": { "balance": 15000.5 }
    }
  ],
  "recent_transactions": [
    {
      "timestamp": "2024-12-27T10:30:00Z",
      "transaction_type": "debit",
      "amount": -50.0,
      "currency": "EUR",
      "description": "Supermercado",
      "extra": null
    }
  ]
}
```

### GET /customers/{subject_key}/snapshot

Snapshot de cualquier cliente (solo employees).

**Auth**: Bearer Token requerido (user_type: employee)

---

## Admin - Users

Todos los endpoints de admin requieren `user_type: employee` y `role: admin`.

### GET /api/admin/users

Listar todos los usuarios.

**Query Params**:

- `include_inactive` (bool): Incluir usuarios deshabilitados
- `user_type` (string): Filtrar por "customer" o "employee"

**Respuesta** (200 OK):

```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "user_type": "employee",
      "role": "admin",
      "dlp_level": "standard",
      "status": "active",
      "can_access_all_subjects": true,
      "subject_ids": []
    }
  ],
  "total": 1
}
```

### POST /api/admin/users

Crear nuevo usuario.

**Request**:

```json
{
  "username": "nuevo_usuario",
  "password": "password_seguro_123",
  "user_type": "customer",
  "role": "user",
  "display_name": "Nuevo Usuario",
  "dlp_level": "standard",
  "can_access_all_subjects": false,
  "subject_ids": ["CLI-81095"],
  "full_name": "Nombre Completo",
  "document_id": "12345678A",
  "tax_id": "12345678A",
  "email": "usuario@ejemplo.com",
  "phone": "+34612345678"
}
```

### GET /api/admin/users/{user_id}

Obtener usuario por ID.

### PUT /api/admin/users/{user_id}

Actualizar usuario.

**Request**:

```json
{
  "role": "admin",
  "dlp_level": "privileged",
  "status": "active",
  "can_access_all_subjects": true,
  "new_password": "nuevo_password_123"
}
```

### DELETE /api/admin/users/{user_id}

Eliminar o desactivar usuario.

**Query Params**:

- `hard_delete` (bool): Si `true`, elimina permanentemente. Default: `false` (soft delete)

---

## Admin - Documents

### POST /api/admin/upload-public-document

Subir documento para ingesta.

**Auth**: Bearer Token (admin)

**Content-Type**: `multipart/form-data`

**Form Fields**:

- `file`: Archivo PDF, TXT o MD (máx 50MB)
- `category`: `public_docs` o `educational`

```bash
curl -X POST http://localhost:8088/api/admin/upload-public-document \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@documento.pdf" \
  -F "category=public_docs"
```

**Respuesta** (200 OK):

```json
{
  "success": true,
  "message": "Document uploaded and processed",
  "filename": "abc12345_documento.pdf",
  "file_size": 1234567,
  "file_hash": "sha256_hash_aquí",
  "audit_id": 42,
  "ingestion_status": "success",
  "documents_ingested": 15,
  "category": "public_docs"
}
```

### POST /admin/refresh-public-docs

Re-ingestar todos los PDFs del directorio de documentación.

**Auth**: Bearer Token (admin)

**Respuesta** (200 OK):

```json
{
  "status": "ok",
  "documents_ingested": 25
}
```

---

## Admin - Products & Transactions

### GET /api/admin/subjects

Listar todos los subjects con conteo de productos.

**Respuesta** (200 OK):

```json
{
  "subjects": [
    {
      "id": 1,
      "subject_key": "CLI-81093",
      "subject_type": "person",
      "display_name": "Juan García",
      "status": "active",
      "product_count": 3
    }
  ],
  "total": 1
}
```

### GET /api/admin/subjects/{subject_key}/products

Listar productos de un subject.

### POST /api/admin/subjects/{subject_key}/products

Crear nuevo producto.

**Request**:

```json
{
  "service_type": "bank_account",
  "service_key": "ES9876543210987654321098",
  "status": "active",
  "extra_metadata": { "currency": "EUR", "type": "savings" }
}
```

### PUT /api/admin/products/{product_id}

Actualizar producto.

### DELETE /api/admin/products/{product_id}

Eliminar producto (soft delete por defecto).

### GET /api/admin/products/{product_id}/transactions

Listar transacciones de un producto.

**Query Params**:

- `limit` (int): Máximo resultados (default: 50, max: 500)
- `offset` (int): Offset para paginación
- `tx_type` (string): Filtrar por tipo

### POST /api/admin/products/{product_id}/transactions

Crear nueva transacción.

**Request**:

```json
{
  "transaction_type": "credit",
  "amount": 1500.0,
  "currency": "EUR",
  "description": "Transferencia recibida",
  "extra_metadata": { "reference": "TRF-123456" }
}
```

### PUT /api/admin/transactions/{transaction_id}

Actualizar transacción.

### DELETE /api/admin/transactions/{transaction_id}

Eliminar transacción (hard delete).

---

## Admin - Subject Data

### GET /api/admin/subjects/{subject_key}/data

Obtener datos completos de un subject para edición.

**Respuesta** (200 OK):

```json
{
  "subject_key": "CLI-81093",
  "subject_type": "person",
  "display_name": "Juan García",
  "status": "active",
  "full_name": "Juan García Pérez",
  "document_id": "12345678A",
  "tax_id": "12345678A",
  "email": "juan.garcia@ejemplo.com",
  "phone": "+34612345678",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-12-27T15:00:00Z"
}
```

### PUT /api/admin/subjects/{subject_key}/data

Actualizar datos de subject con auditoría.

**Request**:

```json
{
  "display_name": "Juan García Pérez",
  "email": "nuevo.email@ejemplo.com",
  "reason": "Actualización por solicitud del cliente vía ticket #12345"
}
```

> **Importante**: El campo `reason` es obligatorio (mín 10 caracteres) para documentar el cambio.

### GET /api/admin/subjects/{subject_key}/history

Historial de modificaciones de un subject.

**Respuesta** (200 OK):

```json
[
  {
    "audit_id": 123,
    "timestamp": "2024-12-27T15:00:00Z",
    "operator_user_id": "1",
    "operator_username": "admin",
    "outcome": "success",
    "details": {
      "changes": ["email"],
      "reason": "Actualización por solicitud del cliente"
    }
  }
]
```

---

## Admin - Audit Log

### GET /admin/audit-log

Consultar log de auditoría.

**Query Params**:

- `user_id` (string): Filtrar por usuario
- `subject_key` (string): Filtrar por subject
- `operation` (string): Filtrar por operación
- `limit` (int): Máximo resultados (default: 200, max: 1000)

**Respuesta** (200 OK):

```json
[
  {
    "id": 456,
    "user_id": "1",
    "username": "admin",
    "subject_key": "CLI-81093",
    "operation": "query",
    "outcome": "success",
    "details": { "duration_sec": 1.23 },
    "created_at": "2024-12-27T15:30:00Z"
  }
]
```

---

## System Setup

### GET /api/system/status

Estado del sistema para setup wizard.

**Auth**: No requerida (para first-run)

**Query Params**:

- `check_llm` (bool): Verificar LLM (más lento)
- `include_errors` (bool): Incluir mensajes de error detallados

**Respuesta** (200 OK):

```json
{
  "database": {
    "connected": true,
    "first_run": false,
    "admin_exists": true
  },
  "qdrant": {
    "connected": true,
    "collection_exists": true,
    "document_count": 1234
  },
  "llm": {
    "configured": true,
    "provider": "hf"
  },
  "system": {
    "version": "0.1.0-beta"
  }
}
```

### POST /api/setup/create-admin

Crear usuario admin inicial (solo disponible en first-run).

**Auth**: No requerida

**Request**:

```json
{
  "username": "admin",
  "password": "password_seguro_minimo_12_caracteres",
  "display_name": "Administrador"
}
```

**Errores**:

- `403`: Ya existe un admin (first_run = false)
- `422`: Password no cumple requisitos

### POST /api/system/init-qdrant

Inicializar colección de Qdrant.

**Auth**: Bearer Token (admin)

---

## Demo Mode

### GET /api/demo/status

Estado del modo demo (si está habilitado).

**Auth**: No requerida

**Respuesta** (200 OK):

```json
{
  "demo_reset_enabled": true,
  "next_reset": "2024-12-27T16:00:00Z",
  "seconds_until_reset": 1800,
  "reset_interval_hours": 1
}
```

---

## Metrics

### GET /metrics

Métricas en formato Prometheus.

**Auth**: No requerida

**Content-Type**: `text/plain`

```
# HELP cortex_query_latency_seconds Query processing latency
# TYPE cortex_query_latency_seconds histogram
cortex_query_latency_seconds_bucket{le="0.1"} 10
cortex_query_latency_seconds_bucket{le="0.5"} 50
cortex_query_latency_seconds_bucket{le="1.0"} 95
cortex_query_latency_seconds_count 100
cortex_query_latency_seconds_sum 45.67

# HELP cortex_http_requests_total Total HTTP requests
# TYPE cortex_http_requests_total counter
cortex_http_requests_total{endpoint="/query",status_class="2xx"} 100
cortex_http_requests_total{endpoint="/query",status_class="4xx"} 5
```

---

## Códigos de Error

| Código | Significado           | Acción Sugerida                    |
| ------ | --------------------- | ---------------------------------- |
| 400    | Bad Request           | Verificar formato del request      |
| 401    | Unauthorized          | Obtener nuevo token                |
| 403    | Forbidden             | Verificar permisos del usuario     |
| 404    | Not Found             | Verificar ID/path del recurso      |
| 409    | Conflict              | Recurso ya existe                  |
| 413    | Payload Too Large     | Reducir tamaño del request         |
| 422    | Unprocessable Entity  | Corregir datos de entrada          |
| 429    | Too Many Requests     | Esperar según `Retry-After` header |
| 500    | Internal Server Error | Reportar bug con request_id        |
| 503    | Service Unavailable   | Reintentar después                 |

---

## Rate Limiting

- **Límite por defecto**: 120 queries por minuto por usuario
- **Burst**: Configurable vía `CKA_RATE_LIMIT_BURST`
- **Window**: 60 segundos (configurable)

Cuando se excede el límite:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 5

{"detail": "rate_limited"}
```

---

## Headers de Seguridad

Todas las respuestas incluyen:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
X-Request-ID: abc123def456
```

Con `CKA_HTTPS_ENABLED=true`:

```http
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; ...
```

---

<p align="center">
  <a href="architecture.md">← Arquitectura</a> •
  <a href="configuration.md">Configuración →</a>
</p>
