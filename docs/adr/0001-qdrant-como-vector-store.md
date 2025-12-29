# ADR 0001: Qdrant como Vector Store

**Estado**: Aceptado  
**Fecha**: 2025-12-01

## Contexto

El sistema requiere una base de datos vectorial que soporte:

- Búsqueda por similitud semántica
- Metadatos asociados a cada vector (payload)
- Despliegue local sencillo para desarrollo

## Decisión

Adoptar **Qdrant** como vector store por su conjunto de características maduro, facilidad de uso con Docker, y excelente cliente Python.

## Alternativas Consideradas

| Alternativa  | Pros                              | Contras                                          |
| ------------ | --------------------------------- | ------------------------------------------------ |
| **FAISS**    | Muy rápido, estándar de industria | Sin persistencia nativa, sin gestión de payloads |
| **Chroma**   | Simple, rápida iteración          | Menos control sobre el schema                    |
| **Weaviate** | Features avanzados                | Footprint operacional más pesado                 |
| **Pinecone** | Managed, escalable                | Costo, dependencia de servicio externo           |

## Consecuencias

### Positivas

- Permite evolución flexible del schema via payload keys
- Simplifica desarrollo local (un solo contenedor)
- Excelente integración con Python

### Negativas

- Requiere script de inicialización de colecciones (`init_qdrant.py`)
- Menos conocido que alternativas como FAISS
