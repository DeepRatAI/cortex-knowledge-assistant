# Registro de Cambios

Todos los cambios notables de Cortex Knowledge Assistant serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [Sin Publicar]

_No hay cambios sin publicar._

## [0.1.0-beta] - 2025-12-29

Primera versión pública beta. 🚀

### Agregado

- **Motor RAG**: Recuperación híbrida con scoring semántico + keywords + tópicos
- **Streaming**: Respuestas en tiempo real via Server-Sent Events
- **Autenticación**: JWT con control de acceso basado en roles
- **Multi-tenancy**: Aislamiento de datos por cliente/subject
- **DLP**: Detección y enmascaramiento de PII (DNI, tarjetas, emails)
- **Observabilidad**: Métricas Prometheus y logging estructurado
- **UI React**: Interfaz de chat moderna con soporte Markdown
- **Mejoras UX**: Iconos Lucide React, tooltips, badges de contexto
- **Docker**: Contenedorización lista para producción con Docker Compose
- **Kubernetes**: Manifiestos K8s para despliegue
- **Testing**: Suite completa con pytest (53 tests)
- **Documentación**: Docs completos (arquitectura, seguridad, API, despliegue)
- **CI/CD**: Pipeline con lint, test, security scan y Docker build

### Stack Técnico

- **Backend**: FastAPI + Python 3.12
- **Frontend**: React 18 + Vite + TypeScript
- **Vector DB**: Qdrant
- **Cache**: Redis
- **LLM**: HuggingFace Inference API
- **Embeddings**: sentence-transformers

### Arquitectura

- Arquitectura hexagonal (Puertos y Adaptadores)
- Diseño domain-agnostic
- Separación clara de responsabilidades

---

## Historial de Versiones

| Versión    | Fecha      | Destacados              |
| ---------- | ---------- | ----------------------- |
| 0.1.0-beta | 2025-12-29 | Primera versión pública |

---

_Hecho con ❤️ por [DeepRatAI](https://github.com/DeepRatAI)_
