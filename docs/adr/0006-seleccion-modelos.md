# ADR 0006: Selección de Modelos LLM

**Estado**: Aceptado  
**Fecha**: 2025-12-01

## Contexto

Se necesita seleccionar el proveedor y modelo LLM para generación de respuestas.
Requisitos:

- Soporte para español
- Costo razonable
- Baja latencia
- Capacidad de streaming

## Decisión

Usar **HuggingFace Inference API** con modelos Mistral/Llama como backend principal.

Modelo por defecto: `mistralai/Mixtral-8x7B-Instruct-v0.1`

## Arquitectura de Proveedores

```
┌─────────────────┐
│   LLMPort       │ ← Interfaz abstracta
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───┴───┐ ┌───┴───┐
│  HF   │ │ Fake  │
│ LLM   │ │ LLM   │
└───────┘ └───────┘
```

## Alternativas Consideradas

| Alternativa           | Pros                     | Contras                 |
| --------------------- | ------------------------ | ----------------------- |
| **OpenAI GPT-4**      | Mejor calidad            | Alto costo, rate limits |
| **Claude**            | Buena calidad            | Menos streaming         |
| **HuggingFace**       | Gratis tier, open models | Menor calidad que GPT-4 |
| **Local (llama.cpp)** | Sin costo                | Requiere GPU potente    |

## Consecuencias

### Positivas

- Tier gratuito para desarrollo
- Modelos open-source
- Fácil cambio de modelo
- Soporte nativo de streaming

### Negativas

- Rate limits en tier gratuito
- Calidad inferior a modelos propietarios top
- Dependencia de servicio externo
