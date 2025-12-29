# ADR 0003: LLM Falso en Tests

**Estado**: Aceptado  
**Fecha**: 2025-12-01

## Contexto

Los tests unitarios no deben depender de APIs externas de LLM porque:

- Son lentos
- Cuestan dinero
- Pueden fallar por problemas de red
- Los resultados no son determinísticos

## Decisión

Implementar un **FakeLLM** que retorna respuestas predecibles para tests.

```python
class FakeLLM(LLMPort):
    def generate(self, prompt: str) -> str:
        return "[TEST] Respuesta generada por FakeLLM"
```

## Alternativas Consideradas

| Alternativa                | Pros              | Contras                            |
| -------------------------- | ----------------- | ---------------------------------- |
| **Mock con unittest.mock** | Flexible          | Verbose, acoplado a implementación |
| **FakeLLM (clase)**        | Simple, tipado    | Menos flexible                     |
| **VCR/cassettes**          | Reproducible      | Complejo de mantener               |
| **Modelo local pequeño**   | Resultados reales | Lento, consume memoria             |

## Consecuencias

### Positivas

- Tests rápidos (<1 segundo)
- Sin costos de API
- Resultados determinísticos
- Tests funcionan offline

### Negativas

- No prueba integración real con LLM
- Requiere tests de integración separados
