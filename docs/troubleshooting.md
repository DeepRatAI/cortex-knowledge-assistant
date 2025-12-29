# Troubleshooting

> Guía de solución de problemas comunes en Cortex.

---

## Problemas de Instalación

### Docker Compose no inicia los servicios

**Síntoma**: `docker compose up -d` falla o los contenedores no se mantienen en ejecución.

**Diagnóstico**:

```bash
docker compose ps        # Ver estado de contenedores
docker compose logs -f   # Ver logs en tiempo real
```

**Causas comunes**:

| Causa              | Solución                                                            |
| ------------------ | ------------------------------------------------------------------- |
| Puerto ocupado     | Verificar que los puertos 3000, 8088, 6333, 6379, 5432 estén libres |
| Docker sin memoria | Aumentar recursos asignados a Docker                                |
| Imagen corrupta    | `docker compose build --no-cache`                                   |

### Error: "Cannot connect to Docker daemon"

**Síntoma**: Cualquier comando de Docker falla con error de conexión.

**Solución**:

```bash
# Verificar que Docker está corriendo
sudo systemctl status docker

# Iniciar si está detenido
sudo systemctl start docker

# Verificar permisos del usuario
sudo usermod -aG docker $USER
# Cerrar sesión y volver a entrar
```

---

## Problemas de Configuración

### Error: "HUGGINGFACE_API_TOKEN not set"

**Síntoma**: El servicio API no inicia o el chat no genera respuestas.

**Solución**:

1. Obtener token en https://huggingface.co/settings/tokens
2. Agregar al archivo `.env`:
   ```env
   HUGGINGFACE_API_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx
   ```
3. Reiniciar servicios: `docker compose restart cortex-api`

### Error: "JWT_SECRET must be set"

**Síntoma**: Error de autenticación o servicios que no inician.

**Solución**:

```env
# .env
CKA_JWT_SECRET=tu-clave-secreta-minimo-32-caracteres
```

> **Seguridad**: En producción, usa una clave generada aleatoriamente de al menos 64 caracteres.

### Variables de entorno no se aplican

**Síntoma**: Cambios en `.env` no tienen efecto.

**Solución**:

```bash
# Recrear contenedores para aplicar cambios
docker compose down
docker compose up -d
```

---

## Problemas de Conexión

### Error: "Cannot connect to Qdrant"

**Síntoma**: El chat falla con error de conexión a base vectorial.

**Diagnóstico**:

```bash
# Verificar que Qdrant está corriendo
docker compose ps cortex-qdrant

# Verificar logs
docker compose logs cortex-qdrant

# Probar conexión
curl http://localhost:6333/health
```

**Soluciones**:

| Causa                  | Solución                                            |
| ---------------------- | --------------------------------------------------- |
| Contenedor no iniciado | `docker compose up -d cortex-qdrant`                |
| Host incorrecto        | Verificar `CKA_QDRANT_HOST=cortex-qdrant` en `.env` |
| Red de Docker          | `docker network ls` y verificar que existe la red   |

### Error: "Cannot connect to Redis"

**Síntoma**: Rate limiting o sesiones no funcionan.

**Diagnóstico**:

```bash
docker compose ps cortex-redis
docker compose logs cortex-redis
```

**Solución**:

```bash
docker compose restart cortex-redis
```

### Error: "Cannot connect to PostgreSQL"

**Síntoma**: Login falla, usuarios no se pueden crear.

**Diagnóstico**:

```bash
docker compose ps cortex-postgres
docker compose logs cortex-postgres
```

**Soluciones**:

| Causa                    | Solución                                              |
| ------------------------ | ----------------------------------------------------- |
| Primera ejecución        | Esperar ~30s para inicialización de la DB             |
| Volumen corrupto         | `docker compose down -v` y reiniciar (ADVERTENCIA: borra datos) |
| Credenciales incorrectas | Verificar `CKA_POSTGRES_*` en `.env`                  |

---

## Problemas del Chat / RAG

### El chat tarda mucho en responder (~10+ segundos)

**Síntoma**: Primera respuesta muy lenta.

**Explicación**: Es comportamiento normal. El modelo LLM necesita inicializarse en la primera consulta (cold start).

**Mitigación**:

- La UI muestra "Generando..." durante el proceso
- Respuestas subsiguientes son más rápidas (2-5s)

### El chat no responde o devuelve error

**Síntoma**: Error 500 o timeout en consultas.

**Diagnóstico**:

```bash
docker compose logs cortex-api | tail -50
```

**Causas comunes**:

| Causa                         | Solución                                  |
| ----------------------------- | ----------------------------------------- |
| Token de HuggingFace inválido | Verificar token y permisos en HuggingFace |
| Qdrant sin documentos         | Ejecutar ingesta de documentos            |
| Límite de rate en HuggingFace | Esperar o usar cuenta Pro                 |

### Las respuestas no son relevantes

**Síntoma**: El asistente responde pero sin contexto correcto.

**Causas posibles**:

| Causa                      | Solución                                        |
| -------------------------- | ----------------------------------------------- |
| Documentos no indexados    | Verificar en Admin > Documentos > Estado RAG    |
| Contexto incorrecto        | Verificar selector de contexto (Employee/Admin) |
| Embeddings desactualizados | Re-indexar documentos                           |

---

## Problemas de Autenticación

### Error: "Invalid credentials"

**Síntoma**: Login falla con credenciales correctas.

**Diagnóstico**:

```bash
# Verificar que PostgreSQL está corriendo y tiene datos
docker compose exec cortex-postgres psql -U cortex -d cortex -c "SELECT username FROM users;"
```

**Soluciones**:

| Causa                 | Solución                                     |
| --------------------- | -------------------------------------------- |
| Usuario no existe     | Crear usuario desde Admin o first-run wizard |
| Contraseña incorrecta | Resetear desde Admin panel                   |
| Base de datos vacía   | Verificar migración inicial                  |

### Error: "Token expired"

**Síntoma**: Sesión se cierra inesperadamente.

**Explicación**: Los tokens JWT tienen expiración configurable (default: 24h).

**Solución**: Volver a hacer login.

### Error: "Insufficient permissions"

**Síntoma**: Acción bloqueada con error de permisos.

**Causa**: El rol del usuario no tiene permisos para esa acción.

**Solución**: Verificar el rol asignado en Admin > Usuarios.

---

## Problemas de Producción

### CORS errors en el navegador

**Síntoma**: Errores de CORS en la consola del navegador.

**Solución**:

```env
# .env
CKA_CORS_ORIGINS=https://tu-dominio.com,https://api.tu-dominio.com
```

### Certificados SSL / HTTPS

**Síntoma**: Navegador muestra advertencia de seguridad.

**Solución con Cloudflare Tunnel**:

```bash
cloudflared tunnel run --token YOUR_TOKEN
```

El tunnel proporciona HTTPS automático sin configuración adicional.

### Health checks fallan en Kubernetes

**Síntoma**: Pods reiniciándose continuamente.

**Diagnóstico**:

```bash
kubectl logs -f deployment/cortex-api
kubectl describe pod cortex-api-xxx
```

**Verificar endpoints**:

```bash
curl http://localhost:8088/health  # Liveness
curl http://localhost:8088/ready   # Readiness
```

---

## Problemas Conocidos (Beta)

### Historial de documentos muestra error JSON

**Síntoma**: En Admin > Documentos > Historial aparece error de parsing JSON.

**Estado**: Bug conocido en Beta. El historial de cargas está en desarrollo.

**Workaround**: Verificar estado de documentos en la pestaña "Estado RAG".

### Botones sin tooltips

**Síntoma**: Botones [E], [D] no explican su función.

**Estado**: Mejora planificada para v1.0.0.

**Referencia**: Los botones son: [E] = Editar, [D] = Detalles.

---

## Obtener Ayuda

Si el problema persiste:

1. **Revisar logs completos**:

   ```bash
   docker compose logs > cortex-debug.log 2>&1
   ```

2. **Verificar versión**:

   ```bash
   docker compose exec cortex-api python -c "import cortex_ka; print(cortex_ka.__version__)"
   ```

3. **Reportar issue**: [GitHub Issues](https://github.com/DeepRatAI/cortex-knowledge-assistant/issues)

   Incluir:

   - Versión de Cortex
   - Sistema operativo
   - Logs relevantes
   - Pasos para reproducir

---

<p align="center">
  <a href="configuration.md">Configuración</a> |
  <a href="index.md">Índice</a>
</p>
