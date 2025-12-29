# Guía de Contribución

¡Gracias por tu interés en contribuir a Cortex Knowledge Assistant!

## Tabla de Contenidos

- [Código de Conducta](#código-de-conducta)
- [Primeros Pasos](#primeros-pasos)
- [Configuración del Entorno](#configuración-del-entorno)
- [Realizar Cambios](#realizar-cambios)
- [Proceso de Pull Request](#proceso-de-pull-request)
- [Guías de Estilo](#guías-de-estilo)

## Código de Conducta

Este proyecto se adhiere al [Código de Conducta del Contributor Covenant](CODE_OF_CONDUCT.md). Al participar, te comprometes a respetar este código.

## Primeros Pasos

### Issues

- **Reportar Bugs**: Usa la plantilla de bug report
- **Sugerir Features**: Usa la plantilla de feature request
- **Preguntas**: Abre una discusión en la pestaña Discussions

### Good First Issues

Busca issues etiquetadas con `good first issue` - son excelentes puntos de partida para nuevos contribuidores.

## Configuración del Entorno

### Requisitos Previos

- Python 3.12+
- Node.js 18+
- Docker y Docker Compose
- Git

### Setup Local

```bash
# 1. Fork y clonar el repositorio
git clone https://github.com/TU_USUARIO/cortex-knowledge-assistant.git
cd cortex-knowledge-assistant

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -e ".[dev]"

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu HF_API_KEY

# 5. Iniciar infraestructura
docker compose up -d qdrant redis postgres

# 6. Ejecutar la API (en una terminal)
uvicorn src.cortex_ka.api.main:app --reload --port 8088

# 7. Ejecutar la UI (en otra terminal)
cd ui && npm install && npm run dev
```

### Ejecutar Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Ejecutar archivo de tests específico
pytest tests/test_pii.py -v

# Ejecutar con cobertura
pytest tests/ --cov=cortex_ka --cov-report=html
```

## Realizar Cambios

### Nomenclatura de Ramas

- `feature/descripcion` - Nuevas funcionalidades
- `fix/descripcion` - Corrección de bugs
- `docs/descripcion` - Cambios de documentación
- `refactor/descripcion` - Refactorización de código

### Mensajes de Commit

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(<alcance>): <descripción>

[cuerpo opcional]

[pie opcional]
```

Tipos:

- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Documentación
- `style`: Formateo
- `refactor`: Reestructuración de código
- `test`: Añadir tests
- `chore`: Mantenimiento

Ejemplos:

```
feat(rag): agregar scoring híbrido con extracción de tópicos
fix(auth): manejar tokens JWT expirados correctamente
docs(readme): actualizar instrucciones de instalación
```

## Proceso de Pull Request

1. **Crear una rama** desde `main`
2. **Realizar cambios** siguiendo las guías de estilo
3. **Ejecutar tests**: `pytest tests/ -v`
4. **Actualizar documentación** si es necesario
5. **Enviar PR** con descripción clara

### Checklist del PR

- [ ] Los tests pasan localmente (`pytest tests/ -v`)
- [ ] El código sigue las guías de estilo
- [ ] Documentación actualizada (si aplica)
- [ ] Mensajes de commit siguen la convención
- [ ] La descripción del PR explica los cambios

## Guías de Estilo

### Python

- **Formateador**: Black (línea máxima 120)
- **Ordenamiento de imports**: isort
- **Linting**: flake8
- **Type hints**: Requeridos para funciones públicas

```python
# Correcto
def calculate_score(query: str, documents: list[str]) -> float:
    """Calcular score de relevancia para documentos."""
    ...

# Incorrecto
def calculate_score(query, documents):
    ...
```

### TypeScript/React

- Usar componentes funcionales con hooks
- Seguir patrones existentes en el codebase
- Usar tipos de TypeScript (evitar `any`)

### Documentación

- Usar Markdown para toda la documentación
- Incluir ejemplos de código cuando sea útil
- Mantener un lenguaje claro y conciso

## ¿Preguntas?

- Abre una Discussion en GitHub
- Menciona a los maintainers en issues
- Contacta por email

---

¡Gracias por contribuir!

_Hecho con ❤️ por [DeepRatAI](https://github.com/DeepRatAI)_
