# ADR 0002: Embeddings Locales

**Estado**: Aceptado  
**Fecha**: 2025-12-01

## Contexto

Se necesita generar embeddings para la búsqueda semántica. Las opciones son:

- API externa (OpenAI, Cohere)
- Modelo local (sentence-transformers)

## Decisión

Usar **sentence-transformers** con modelos locales para generación de embeddings.

Modelo por defecto: `paraphrase-multilingual-MiniLM-L12-v2`

## Alternativas Consideradas

| Alternativa               | Pros                          | Contras                                   |
| ------------------------- | ----------------------------- | ----------------------------------------- |
| **OpenAI Embeddings**     | Alta calidad                  | Costo por uso, latencia de red            |
| **Cohere**                | Buena calidad                 | Dependencia externa, costo                |
| **sentence-transformers** | Gratuito, local, sin latencia | Uso de memoria, calidad ligeramente menor |

## Consecuencias

### Positivas

- Sin costos de API
- Sin dependencia de servicios externos
- Baja latencia (local)
- Funciona offline

### Negativas

- Consumo de memoria (~500MB por modelo)
- Primera carga del modelo lenta
- Requiere GPU para mejor rendimiento (opcional)
