# Cortex Knowledge Assistant - Documentación

<p align="center">
  <strong>Sistema RAG de nivel empresarial con protección de datos sensibles</strong>
</p>

<p align="center">
  <a href="getting-started.md">Inicio Rápido</a> •
  <a href="architecture.md">Arquitectura</a> •
  <a href="api-reference.md">API Reference</a> •
  <a href="configuration.md">Configuración</a> •
  <a href="security.md">Seguridad</a> •
  <a href="deployment.md">Despliegue</a> •
  <a href="development.md">Desarrollo</a>
</p>

---

## Índice de Documentación

### Guías Principales

| Documento                               | Descripción                                         | Audiencia                           |
| --------------------------------------- | --------------------------------------------------- | ----------------------------------- |
| [**Inicio Rápido**](getting-started.md) | Instalación y primer uso en menos de 5 minutos      | Todos                               |
| [**Guías de Usuario**](user-guides.md)  | Uso del sistema por rol (Customer, Employee, Admin) | Usuarios finales                    |
| [**Arquitectura**](architecture.md)     | Diseño técnico, componentes y flujo de datos        | Arquitectos, Desarrolladores Senior |
| [**API Reference**](api-reference.md)   | Referencia completa de endpoints REST               | Desarrolladores                     |
| [**Configuración**](configuration.md)   | Variables de entorno y opciones de configuración    | DevOps, Administradores             |
| [**Seguridad**](security.md)            | Autenticación, autorización, DLP y PII              | Security Engineers                  |
| [**Despliegue**](deployment.md)         | Docker, Kubernetes, producción                      | DevOps, SRE                         |
| [**Desarrollo**](development.md)        | Tests, contribución, arquitectura interna           | Desarrolladores                     |

### Recursos Adicionales

| Documento                                   | Descripción                             |
| ------------------------------------------- | --------------------------------------- |
| [Troubleshooting](troubleshooting.md)       | Solución de problemas comunes           |
| [ADR (Architecture Decision Records)](adr/) | Decisiones de arquitectura documentadas |
| [Roadmap](ROADMAP.md)                       | Features planificadas para v1.0.0       |
| [CHANGELOG](../CHANGELOG.md)                | Historial de cambios por versión        |
| [CONTRIBUTING](../CONTRIBUTING.md)          | Guía de contribución                    |

---

## ¿Qué es Cortex?

Cortex Knowledge Assistant es un sistema **Retrieval-Augmented Generation (RAG)** de nivel empresarial diseñado para:

- **Búsqueda semántica** sobre documentación corporativa
- **Generación de respuestas** contextualizadas con LLM
- **Protección automática** de información sensible (PII/DLP)
- **Multi-tenancy** con control de acceso basado en roles
- **Integración transaccional** para consultas sobre datos de clientes

### Casos de Uso

- **Banca**: Asistente para consultas sobre productos, movimientos y normativas
- **Educación**: Sistema de ayuda para estudiantes con acceso a material académico
- **Corporativo**: Base de conocimiento interna con acceso controlado

---

## Stack Tecnológico

| Componente       | Tecnología                   | Propósito                          |
| ---------------- | ---------------------------- | ---------------------------------- |
| **Backend API**  | FastAPI (Python 3.12)        | API REST con streaming SSE         |
| **Frontend**     | React 18 + TypeScript + Vite | Interfaz de usuario                |
| **Vector Store** | Qdrant                       | Búsqueda semántica                 |
| **Cache**        | Redis                        | Rate limiting, sesiones            |
| **Database**     | PostgreSQL 16                | Usuarios, transacciones, auditoría |
| **LLM**          | HuggingFace Inference API    | Generación de respuestas           |
| **Embeddings**   | sentence-transformers        | Vectorización de documentos        |

---

## Inicio Rápido

```bash
# 1. Clonar el repositorio
git clone https://github.com/DeepRatAI/cortex-knowledge-assistant.git
cd cortex-knowledge-assistant

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu API key de HuggingFace

# 3. Iniciar con Docker Compose
docker compose up -d

# 4. Acceder a la UI
open http://localhost:3000
```

Para una guía detallada, ver [Inicio Rápido](getting-started.md).

---

## Navegación por Perfil

### Para Usuarios del Sistema

1. [Guías de Usuario](user-guides.md) - Cómo usar Cortex según tu rol
2. [Troubleshooting](troubleshooting.md) - Solución de problemas comunes

### Para Desarrolladores

1. [Inicio Rápido](getting-started.md) - Configurar entorno de desarrollo
2. [Arquitectura](architecture.md) - Entender el diseño del sistema
3. [API Reference](api-reference.md) - Endpoints disponibles
4. [Desarrollo](development.md) - Tests, linting, contribución

### Para DevOps / SRE

1. [Configuración](configuration.md) - Variables de entorno
2. [Despliegue](deployment.md) - Docker, Kubernetes, producción
3. [Seguridad](security.md) - Headers, rate limiting, compliance
4. [Troubleshooting](troubleshooting.md) - Diagnóstico de problemas

### Para Arquitectos

1. [Arquitectura](architecture.md) - Diseño hexagonal, componentes
2. [ADR](adr/) - Decisiones de arquitectura documentadas
3. [Seguridad](security.md) - Modelo de seguridad
4. [Roadmap](ROADMAP.md) - Evolución planificada

---

## Enlaces Útiles

- **Demo en Vivo**: [cortex.deeprat.tech](https://cortex.deeprat.tech)
- **Repositorio**: [GitHub](https://github.com/DeepRatAI/cortex-knowledge-assistant)
- **Reportar Issues**: [GitHub Issues](https://github.com/DeepRatAI/cortex-knowledge-assistant/issues)

---

## Licencia

Cortex Knowledge Assistant está disponible bajo **licencia dual**:

- **AGPL-3.0** para uso open source
- **Licencia comercial** para uso empresarial privado

Contacto: deeprat.tec@gmail.com

---

<p align="center">
  <sub>Documentación para Cortex Beta</sub>
</p>
