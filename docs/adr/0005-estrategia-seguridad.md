# ADR 0005: Estrategia de Seguridad

**Estado**: Aceptado  
**Fecha**: 2025-12-01

## Contexto

El sistema maneja información sensible (PII) y requiere:

- Autenticación robusta
- Control de acceso granular
- Protección de datos sensibles
- Aislamiento multi-tenant

## Decisión

Implementar estrategia de seguridad en capas:

1. **Autenticación**: JWT con tokens de corta duración
2. **Autorización**: RBAC (Role-Based Access Control)
3. **DLP**: Detección y enmascaramiento de PII
4. **Multi-tenancy**: Aislamiento por `subject_id`

## Componentes de Seguridad

| Componente        | Implementación        | Propósito                    |
| ----------------- | --------------------- | ---------------------------- |
| **Auth**          | JWT + Bearer tokens   | Identificar usuarios         |
| **RBAC**          | Roles en JWT claims   | Controlar acceso             |
| **PII Detection** | Regex + clasificación | Identificar datos sensibles  |
| **Masking**       | Redacción automática  | Proteger datos en respuestas |

## Alternativas Consideradas

| Alternativa       | Pros               | Contras                  |
| ----------------- | ------------------ | ------------------------ |
| **OAuth2 + OIDC** | Estándar, delegado | Complejidad, dependencia |
| **JWT propio**    | Simple, stateless  | Manejo de revocación     |
| **Session-based** | Familiar           | Stateful, escalabilidad  |

## Consecuencias

### Positivas

- Autenticación stateless y escalable
- Control de acceso declarativo
- PII protegido automáticamente

### Negativas

- Tokens JWT no revocables fácilmente
- Requiere HTTPS obligatorio en producción
