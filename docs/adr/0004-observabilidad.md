# ADR 0004: Observabilidad y Trazabilidad

**Estado**: Aceptado  
**Fecha**: 2025-12-01

## Contexto

Un sistema RAG en producción necesita:

- Métricas de rendimiento
- Logs estructurados
- Trazabilidad de requests

## Decisión

Implementar stack de observabilidad con:

- **Prometheus**: Métricas (latencia, throughput, errores)
- **Logging estructurado**: JSON logs con contexto
- **Endpoint /metrics**: Exposición de métricas

## Métricas Implementadas

| Métrica                      | Tipo      | Descripción             |
| ---------------------------- | --------- | ----------------------- |
| `rag_query_duration_seconds` | Histogram | Latencia de queries RAG |
| `rag_chunks_retrieved`       | Counter   | Chunks recuperados      |
| `llm_tokens_generated`       | Counter   | Tokens generados        |
| `auth_failures_total`        | Counter   | Fallos de autenticación |

## Alternativas Consideradas

| Alternativa              | Pros               | Contras                   |
| ------------------------ | ------------------ | ------------------------- |
| **OpenTelemetry**        | Estándar, completo | Complejidad de setup      |
| **Prometheus + logging** | Simple, maduro     | Menos trazas distribuidas |
| **Datadog/New Relic**    | Managed, potente   | Costo, vendor lock-in     |

## Consecuencias

### Positivas

- Visibilidad del comportamiento del sistema
- Debugging facilitado con logs estructurados
- Alerting posible vía Prometheus

### Negativas

- Overhead mínimo de instrumentación
- Requiere infraestructura adicional para dashboards
