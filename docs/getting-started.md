# Inicio Rápido

Esta guía te llevará desde cero hasta tener Cortex funcionando en menos de 5 minutos.

---

## Requisitos Previos

| Requisito      | Versión Mínima | Verificar                |
| -------------- | -------------- | ------------------------ |
| Docker         | 24.0+          | `docker --version`       |
| Docker Compose | 2.20+          | `docker compose version` |
| Git            | 2.30+          | `git --version`          |

### Requisito Opcional

- **HuggingFace API Key**: Para generación de respuestas con LLM real (gratuita en [huggingface.co](https://huggingface.co/settings/tokens))

> **Sin API Key**: El sistema funciona con un LLM "Fake" que retorna respuestas de prueba.

---

## Instalación

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/DeepRatAI/cortex-knowledge-assistant.git
cd cortex-knowledge-assistant
```

### Paso 2: Configurar Variables de Entorno

```bash
# Copiar plantilla de configuración
cp .env.example .env
```

Editar `.env` con los valores mínimos:

```env
# === OBLIGATORIO PARA LLM REAL ===
HF_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxxx

# === SEGURIDAD (cambiar en producción) ===
POSTGRES_PASSWORD=tu_password_seguro
JWT_SECRET_KEY=clave_secreta_para_jwt_minimo_32_caracteres

# === OPCIONAL ===
CKA_LLM_PROVIDER=HF  # Usar HuggingFace (o "Fake" para desarrollo)
CKA_USE_QDRANT=true  # Habilitar búsqueda vectorial
CKA_USE_REDIS=true   # Habilitar cache y rate limiting
```

### Paso 3: Iniciar con Docker Compose

```bash
docker compose up -d
```

Este comando:

1. Descarga las imágenes necesarias (Qdrant, Redis, PostgreSQL)
2. Construye las imágenes de Cortex API y UI
3. Inicia todos los servicios
4. Configura la red interna

### Paso 4: Verificar que Todo Funciona

```bash
# Ver estado de los contenedores
docker compose ps

# Verificar health de la API
curl http://localhost:8088/health
```

Respuesta esperada:

```json
{
  "status": "healthy",
  "components": {
    "database": { "healthy": true, "status": "connected" },
    "qdrant": { "healthy": true, "status": "connected", "documents": 0 },
    "llm": { "healthy": true, "provider": "hf", "model": "meta-llama/..." }
  }
}
```

---

## Acceder a la Interfaz

| Servicio         | URL                          | Descripción         |
| ---------------- | ---------------------------- | ------------------- |
| **UI Web**       | http://localhost:3000        | Interfaz de usuario |
| **API**          | http://localhost:8088        | API REST            |
| **Health Check** | http://localhost:8088/health | Estado del sistema  |

---

## Configuración Inicial (First-Run Wizard)

Al acceder por primera vez a http://localhost:3000, verás el **Setup Wizard**:

### 1. Crear Usuario Administrador

El sistema detecta que no hay usuarios y presenta un formulario:

```
Usuario: admin
Contraseña: (mínimo 12 caracteres)
```

> **Importante**: Esta es la única oportunidad de crear el admin sin autenticación.

### 2. Verificar Estado del Sistema

El wizard muestra el estado de cada componente:

- Base de datos conectada
- Qdrant disponible
- LLM configurado

### 3. Inicializar Qdrant (Opcional)

Si Qdrant no tiene la colección de documentos, el wizard ofrece crearla.

---

## Ingestar Documentos

### Desde la UI (Recomendado)

1. Iniciar sesión como administrador
2. Ir a **Admin Panel** → **Gestión de Documentos**
3. Subir archivos PDF, TXT o MD
4. Los documentos se procesan automáticamente

### Desde la API

```bash
# Obtener token de autenticación
TOKEN=$(curl -s -X POST http://localhost:8088/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"tu_password"}' | jq -r .access_token)

# Subir documento
curl -X POST http://localhost:8088/api/admin/upload-public-document \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@mi_documento.pdf" \
  -F "category=public_docs"
```

### Ingesta Masiva de PDFs

Para ingestar todos los PDFs de un directorio:

```bash
# Copiar documentos al volumen de datos
docker cp ./mis_documentos/ cortex_api:/app/data/documentacion/publica/

# Ejecutar ingesta masiva
curl -X POST http://localhost:8088/admin/refresh-public-docs \
  -H "Authorization: Bearer $TOKEN"
```

---

## Tu Primera Consulta

### Desde la UI

1. Iniciar sesión
2. Escribir una pregunta en el chat
3. Cortex buscará en los documentos y generará una respuesta

### Desde la API

```bash
curl -X POST http://localhost:8088/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Cuáles son los requisitos para abrir una cuenta?",
    "session_id": "mi-sesion-1"
  }'
```

Respuesta:

```json
{
  "answer": "Según la documentación, los requisitos para abrir una cuenta son...",
  "used_chunks": ["chunk-id-1", "chunk-id-2"],
  "citations": [{ "id": "chunk-id-1", "source": "requisitos_cuenta.pdf" }],
  "session_id": "mi-sesion-1"
}
```

---

## Comandos Útiles

```bash
# Ver logs de la API
docker compose logs -f cortex-api

# Reiniciar solo la API (después de cambios)
docker compose restart cortex-api

# Detener todo
docker compose down

# Detener y eliminar volúmenes (CUIDADO: borra datos)
docker compose down -v

# Reconstruir imágenes (después de cambios de código)
docker compose build --no-cache
docker compose up -d
```

---

## Solución de Problemas

### La API no inicia

```bash
# Ver logs detallados
docker compose logs cortex-api

# Verificar que los servicios dependientes están healthy
docker compose ps
```

### Error "LLM not configured"

1. Verificar que `HF_API_KEY` está en `.env`
2. Verificar que el key es válido en huggingface.co
3. Reiniciar: `docker compose restart cortex-api`

### Qdrant no se conecta

```bash
# Verificar que Qdrant está corriendo
docker compose logs qdrant

# Reiniciar Qdrant
docker compose restart qdrant
```

### Error de base de datos

```bash
# Ver logs de PostgreSQL
docker compose logs postgres

# Verificar conexión
docker compose exec postgres psql -U cortex -d cortex -c "SELECT 1"
```

---

## Próximos Pasos

- [**Arquitectura**](architecture.md): Entender cómo funciona internamente
- [**Configuración**](configuration.md): Personalizar comportamiento
- [**API Reference**](api-reference.md): Integrar con tus aplicaciones
- [**Seguridad**](security.md): Configurar para producción
- [**Despliegue**](deployment.md): Llevar a producción

---

<p align="center">
  <a href="index.md">← Índice</a> •
  <a href="architecture.md">Arquitectura →</a>
</p>
