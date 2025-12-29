# Seguridad

Documentación completa del modelo de seguridad de Cortex Knowledge Assistant, incluyendo autenticación, autorización, protección de datos y mejores prácticas para producción.

---

## Principios de Seguridad

Cortex implementa un modelo de **defensa en profundidad**:

1. **Autenticación**: JWT tokens con expiración y refresh
2. **Autorización**: RBAC (Role-Based Access Control) + multi-tenancy
3. **Protección de Datos**: DLP/PII redaction automático
4. **Rate Limiting**: Protección contra abuso
5. **Headers de Seguridad**: HSTS, CSP, X-Frame-Options
6. **Auditoría**: Log inmutable de operaciones sensibles

---

## Autenticación

### JWT (JSON Web Tokens)

Cortex utiliza JWT Bearer tokens para autenticar todas las requests.

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Características del Token**:

- Algoritmo: HS256
- Expiración: 24 horas (configurable)
- Claims incluidos: `user_id`, `username`, `user_type`, `role`, `dlp_level`, `subject_ids`, `can_access_all_subjects`

### Flujo de Autenticación

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUJO DE AUTENTICACIÓN                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────┐        POST /auth/login         ┌──────────────┐
│  Cliente │ ──────────────────────────────▶ │  Cortex API  │
│          │    {username, password}         │              │
└──────────┘                                 └──────┬───────┘
                                                    │
                                                    ▼
                                          ┌─────────────────┐
                                          │ 1. Buscar user  │
                                          │ 2. Verify hash  │
                                          │ 3. Check status │
                                          │ 4. Load subjects│
                                          │ 5. Issue JWT    │
                                          └─────────┬───────┘
                                                    │
┌──────────┐        200 OK                          │
│  Cliente │ ◀──────────────────────────────────────┘
│          │    {access_token, user}
└──────────┘

Requests subsiguientes:

┌──────────┐    Authorization: Bearer xxx    ┌──────────────┐
│  Cliente │ ──────────────────────────────▶ │  Cortex API  │
│          │    GET /query                   │              │
└──────────┘                                 └──────┬───────┘
                                                    │
                                                    ▼
                                          ┌─────────────────┐
                                          │ 1. Decode JWT   │
                                          │ 2. Verify sig   │
                                          │ 3. Check expiry │
                                          │ 4. Build context│
                                          └─────────────────┘
```

### Seguridad de Passwords

- **Hashing**: bcrypt con cost factor 12
- **Validación**: Mínimo 12 caracteres para admin
- **Timing-safe comparison**: Evita timing attacks en login

```python
# Nunca se almacenan passwords en texto plano
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12))
```

### Configuración de JWT

```env
# Clave secreta para firmar tokens (OBLIGATORIO cambiar en producción)
JWT_SECRET_KEY=your-super-secret-key-at-least-32-characters

# Expiración del token (por defecto 24h)
JWT_EXPIRATION_HOURS=24
```

---

## - Autorización (RBAC + Multi-Tenancy)

### Roles del Sistema

| Role       | user_type  | Permisos                                                |
| ---------- | ---------- | ------------------------------------------------------- |
| `admin`    | `employee` | Acceso total, endpoints `/admin/*`, gestión de usuarios |
| `user`     | `employee` | Consultas RAG, acceso a subjects asignados              |
| `customer` | `customer` | Solo sus propios datos, sin acceso a `/admin/*`         |

### Multi-Tenancy

El sistema aísla datos por "tenant" usando el concepto de **Subject**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MODELO MULTI-TENANT                                │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────┐
                    │            ADMIN                   │
                    │     can_access_all_subjects=true   │
                    └───────────────┬───────────────────┘
                                    │
                    ┌───────────────▼───────────────────┐
                    │       Todos los Subjects          │
                    │  CLI-001, CLI-002, CLI-003, ...   │
                    └───────────────────────────────────┘

┌─────────────────────────┐           ┌─────────────────────────┐
│       EMPLOYEE          │           │       CUSTOMER          │
│ can_access_all=false    │           │                         │
│ subject_ids=[CLI-001]   │           │ subject_ids=[CLI-002]   │
└───────────┬─────────────┘           └───────────┬─────────────┘
            │                                     │
            ▼                                     ▼
    ┌───────────────┐                     ┌───────────────┐
    │   CLI-001     │                     │   CLI-002     │
    │   (Solo)      │                     │   (Solo)      │
    └───────────────┘                     └───────────────┘
```

### Reglas de Acceso a Datos

```python
# Simplificado de api/main.py

if user_type == "employee":
    if can_access_all_subjects:
        # Admin: puede consultar cualquier subject o docs públicos
        subject_id = requested_subject  # None = solo docs públicos
    else:
        # Empleado limitado: solo sus subjects asignados
        if requested_subject in allowed_subject_ids:
            subject_id = requested_subject
        else:
            subject_id = allowed_subject_ids[0]
else:
    # Customer: SIEMPRE restringido a sus subjects
    if not allowed_subject_ids:
        raise HTTPException(403, "No customer scope assigned")
    subject_id = allowed_subject_ids[0]
```

### Verificación en Qdrant

El retriever filtra documentos por `subject_id`:

```python
# Filtro aplicado en retriever_qdrant.py
filter = {
    "should": [
        {"key": "subject_id", "match": {"value": subject_id}},
        {"is_null": {"key": "subject_id"}}  # Docs públicos
    ]
}
```

---

## Protección de Datos (DLP/PII)

### Data Loss Prevention (DLP)

El sistema aplica redacción automática de información sensible antes de enviar respuestas al cliente.

**Pipeline DLP**:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  LLM Answer  │────▶│  DLP Engine  │────▶│   Cliente    │
│  (Raw)       │     │  (Redact)    │     │  (Sanitized) │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Patrones PII Detectados

| Tipo            | Patrón                                | Reemplazo          |
| --------------- | ------------------------------------- | ------------------ |
| DNI/ID Nacional | `\d{7,9}`                             | `<dni-redacted>`   |
| CUIT/CUIL       | `\d{2}-\d{7,8}-\d`                    | `<cuit-redacted>`  |
| Tarjetas        | `\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}` | `<card-redacted>`  |
| Email           | Pattern estándar                      | `<email-redacted>` |
| Teléfono        | `\+?\d[\d\s\-]{6,}\d`                 | `<phone-redacted>` |

### Ejemplo de Redacción

**Antes (respuesta del LLM)**:

```
El cliente Juan García con DNI 12345678 tiene la tarjeta 4532-1234-5678-9012
y puede contactarlo en juan@email.com o al +54 11 4567-8901.
```

**Después (enviado al cliente)**:

```
El cliente Juan García con DNI <dni-redacted> tiene la tarjeta <card-redacted>
y puede contactarlo en <email-redacted> o al <phone-redacted>.
```

### Niveles de DLP

| dlp_level    | Comportamiento                               |
| ------------ | -------------------------------------------- |
| `standard`   | Redacción completa de PII (default)          |
| `privileged` | Sin redacción (solo para backoffice interno) |

### Clasificación PII en Ingesta

Durante la ingesta de documentos, cada chunk es clasificado por sensibilidad:

```python
class PiiClassification:
    has_pii: bool
    by_type: Dict[str, bool]  # dni, cuit, card, phone, email
    sensitivity: Literal["none", "low", "medium", "high"]
```

**Política de Sensibilidad**:

- `high`: Tarjetas de crédito O múltiples tipos de PII
- `medium`: Un identificador fuerte (DNI, CUIT, email, teléfono)
- `low/none`: Sin PII detectado

### Enmascaramiento PII para Contexto LLM

Antes de incluir datos personales en el prompt del LLM, el sistema aplica enmascaramiento basado en el rol del usuario que realiza la consulta.

**Ubicación**: `src/cortex_ka/application/pii_masking.py`

**Flujo de Enmascaramiento**:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      ENMASCARAMIENTO PII PARA LLM                            │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  CustomerSnapshot│────▶│  mask_snapshot  │────▶│  Prompt Builder │
│  (datos raw)     │     │  (por rol)      │     │  (datos safe)   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │   Reglas por viewer_role │
                    └────────────┬────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
    ┌───────────┐          ┌───────────┐          ┌───────────┐
    │   admin   │          │  support  │          │  customer │
    │ Full data │          │  Parcial  │          │ Mínimo    │
    └───────────┘          └───────────┘          └───────────┘
```

**Matriz de Visibilidad por Rol**:

| Campo       | Admin    | Support               | Customer         |
| ----------- | -------- | --------------------- | ---------------- |
| `dni`       | Completo | Últimos 4             | Últimos 4        |
| `email`     | Completo | Parcial (d\*\*\*@...) | Solo dominio     |
| `phone`     | Completo | Últimos 4             | Solo código país |
| `address`   | Completo | Solo ciudad           | Solo ciudad      |
| `accounts`  | Completo | Completo              | Solo propias     |
| `full_name` | Completo | Completo              | Completo         |

**Ejemplo de Enmascaramiento**:

```python
# Datos originales en CustomerSnapshot
{
    "dni": "12345678",
    "email": "juan.perez@email.com",
    "phone": "+54 11 4567-8901"
}

# Vista para rol 'support'
{
    "dni": "****5678",
    "email": "j***@email.com",
    "phone": "****-8901"
}

# Vista para rol 'customer'
{
    "dni": "****5678",
    "email": "***@email.com",
    "phone": "+54 ****"
}
```

**Implementación**:

```python
from cortex_ka.application.pii_masking import mask_snapshot_for_role

# En rag_service.py durante construcción de contexto
masked = mask_snapshot_for_role(customer_snapshot, viewer_role=current_user.role)
prompt = build_prompt(query, context, masked_snapshot=masked)
```

**Auditoría**:

Todo acceso a datos PII se registra con:

- `viewer_role`: Rol del usuario que accede
- `subject_id`: ID del subject consultado
- `pii_fields_accessed`: Campos PII incluidos en el contexto
- `masking_applied`: Nivel de enmascaramiento aplicado

---

## Rate Limiting

Protección contra abuso y DDoS.

### Configuración

```env
CKA_RATE_LIMIT_QPM=120       # Queries por minuto
CKA_RATE_LIMIT_BURST=10      # Capacidad de burst
CKA_RATE_LIMIT_WINDOW_SECONDS=60  # Ventana de tiempo
```

### Implementación

- **Algoritmo**: Token bucket con sliding window
- **Key**: Por `user_id` o `api_key`
- **Storage**: Redis (producción) o in-memory (desarrollo)

### Respuesta 429

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 5
Content-Type: application/json

{"detail": "rate_limited"}
```

---

## Headers de Seguridad

### Headers Siempre Presentes

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
X-Request-ID: abc123def456
```

### Headers con HTTPS Habilitado

Con `CKA_HTTPS_ENABLED=true`:

```http
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'
```

### Configuración CSP

```env
CKA_CSP_POLICY=default-src 'self'; script-src 'self' https://trusted-cdn.com
```

---

## Auditoría

Todas las operaciones sensibles se registran en un log de auditoría inmutable.

### Operaciones Auditadas

| Operación                      | Descripción                          |
| ------------------------------ | ------------------------------------ |
| `login`                        | Intento de login (exitoso o fallido) |
| `query`                        | Consulta RAG realizada               |
| `admin_create_user`            | Creación de usuario                  |
| `admin_update_user`            | Modificación de usuario              |
| `admin_delete_user`            | Eliminación de usuario               |
| `admin_create_product`         | Creación de producto                 |
| `admin_create_transaction`     | Creación de transacción              |
| `admin_update_subject_data`    | Modificación de datos de cliente     |
| `admin_load_demo_transactions` | Carga de datos demo                  |
| `refresh_public_docs`          | Re-ingesta de documentos             |

### Estructura del Audit Log

```json
{
  "id": 456,
  "user_id": "1",
  "username": "admin",
  "subject_key": "CLI-81093",
  "operation": "query",
  "outcome": "success",
  "details": {
    "duration_sec": 1.23,
    "query": "¿Cuál es mi saldo?"
  },
  "created_at": "2024-12-27T15:30:00Z"
}
```

### Consultar Audit Log

```bash
curl -X GET "http://localhost:8088/admin/audit-log?limit=100&operation=login" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Protección de Red

### CORS

```env
CKA_CORS_ORIGINS=https://cortex.example.com,https://admin.example.com
```

**Producción**: Siempre especificar orígenes explícitos, nunca `*`.

### Exposición de Puertos

En producción, solo exponer:

- Puerto `443` (HTTPS) - vía reverse proxy

**NO exponer directamente**:

- `:8088` (API)
- `:6333` (Qdrant)
- `:5432` (PostgreSQL)
- `:6379` (Redis)

### Network Policies (Kubernetes)

```yaml
# k8s/networkpolicies/cortex-api.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: cortex-api
spec:
  podSelector:
    matchLabels:
      app: cortex-api
  ingress:
   - from:
       - podSelector:
            matchLabels:
              app: nginx-ingress
      ports:
       - port: 8088
  egress:
   - to:
       - podSelector:
            matchLabels:
              app: qdrant
      ports:
       - port: 6333
   - to:
       - podSelector:
            matchLabels:
              app: postgres
      ports:
       - port: 5432
   - to:
       - podSelector:
            matchLabels:
              app: redis
      ports:
       - port: 6379
```

---

## Gestión de Secretos

### Desarrollo

```env
# .env (NO commitear)
JWT_SECRET_KEY=dev-secret-key
HF_API_KEY=hf_xxxx
POSTGRES_PASSWORD=dev_password
```

### Producción

Usar gestores de secretos:

**Docker Swarm**:

```yaml
secrets:
  jwt_secret:
    external: true
```

**Kubernetes**:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cortex-secrets
data:
  JWT_SECRET_KEY: base64_encoded_value
  HF_API_KEY: base64_encoded_value
```

**Vault/AWS Secrets Manager**: Integrar vía init container o sidecar.

---

## - Checklist de Seguridad para Producción

### Antes del Despliegue

- [ ] Generar `JWT_SECRET_KEY` único (mín 32 chars)
- [ ] Cambiar `POSTGRES_PASSWORD` del default
- [ ] Configurar `CKA_CORS_ORIGINS` con orígenes específicos
- [ ] Habilitar `CKA_HTTPS_ENABLED=true`
- [ ] Deshabilitar `CKA_ENABLE_DEMO_API_KEY=false`
- [ ] Configurar `CKA_CONFIDENTIAL_RETRIEVAL_ONLY=true` si aplica
- [ ] Revisar y ajustar `CKA_CSP_POLICY`

### Infraestructura

- [ ] Usar HTTPS con certificados válidos
- [ ] Configurar reverse proxy (nginx/traefik)
- [ ] No exponer puertos internos públicamente
- [ ] Configurar firewall/security groups
- [ ] Habilitar Network Policies en Kubernetes

### Monitoreo

- [ ] Configurar alertas para errores 401/403 excesivos
- [ ] Monitorear rate limiting (429s)
- [ ] Revisar audit log periódicamente
- [ ] Configurar log rotation

### Backup

- [ ] Backup automático de PostgreSQL
- [ ] Backup de Qdrant (snapshots)
- [ ] Test de restauración periódico

---

## Respuesta a Incidentes

### Token Comprometido

1. Identificar el `user_id` afectado
2. Deshabilitar usuario: `PUT /api/admin/users/{id}` con `status: inactive`
3. Rotar `JWT_SECRET_KEY` (invalida TODOS los tokens)
4. Revisar audit log para actividad sospechosa

### Brute Force Detectado

1. Revisar audit log: `operation=login, outcome=failure`
2. Identificar IP/usuario atacado
3. Considerar bloqueo temporal a nivel de WAF/firewall
4. Incrementar `CKA_RATE_LIMIT_QPM` si es necesario

### Leak de Datos

1. Identificar alcance vía audit log
2. Verificar que DLP estuvo activo (`CKA_DLP_ENABLED=true`)
3. Notificar según regulación (GDPR, CCPA, etc.)
4. Revisar logs de acceso a subjects afectados

---

## Referencias

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)

---

<p align="center">
  <a href="configuration.md">← Configuración</a> •
  <a href="deployment.md">Despliegue →</a>
</p>
