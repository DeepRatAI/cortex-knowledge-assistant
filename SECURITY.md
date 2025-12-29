# Política de Seguridad

## Versiones Soportadas

| Versión | Soportada          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reportar una Vulnerabilidad

Nos tomamos la seguridad de Cortex Knowledge Assistant muy en serio. Si crees que has encontrado una vulnerabilidad de seguridad, por favor repórtala como se describe a continuación.

### Cómo Reportar

**Por favor NO reportes vulnerabilidades de seguridad a través de issues públicos de GitHub.**

En su lugar, repórtalas por email a:

**deeprat.tec@gmail.com**

**Asunto obligatorio**: `[SECURITY] Descripción breve del problema`

Por favor incluye la siguiente información:

- Tipo de vulnerabilidad (ej: inyección SQL, XSS, bypass de autenticación)
- Rutas completas de los archivos fuente relacionados con la vulnerabilidad
- Ubicación del código fuente afectado (tag/branch/commit o URL directa)
- Instrucciones paso a paso para reproducir el problema
- Prueba de concepto o código de exploit (si es posible)
- Impacto del problema, incluyendo cómo un atacante podría explotarlo

### Qué Esperar

- **Confirmación**: Confirmaremos la recepción de tu reporte de vulnerabilidad dentro de 48 horas.
- **Comunicación**: Te mantendremos informado del progreso hacia una solución.
- **Resolución**: Nuestro objetivo es resolver vulnerabilidades críticas dentro de 7 días.
- **Crédito**: Te daremos crédito en el advisory de seguridad (a menos que prefieras permanecer anónimo).

### Safe Harbor

Apoyamos safe harbor para investigadores de seguridad que:

- Hacen un esfuerzo de buena fe para evitar violaciones de privacidad, destrucción de datos e interrupción o degradación de nuestros servicios
- Solo interactúan con cuentas que les pertenecen o con permiso explícito del titular de la cuenta
- No explotan un problema de seguridad para propósitos distintos a la verificación
- Reportan vulnerabilidades de manera oportuna

## Mejores Prácticas de Seguridad para Usuarios

### Variables de Entorno

- **Nunca hagas commit** de archivos `.env` al control de versiones
- Usa valores **fuertes y únicos** para `CKA_JWT_SECRET`
- Rota las API keys periódicamente
- Usa configuraciones específicas por entorno

### Despliegue

- Ejecuta contenedores como usuarios **no-root** (predeterminado en nuestras imágenes)
- Mantén las imágenes Docker **actualizadas**
- Usa **HTTPS** en producción
- Habilita el modo **read-only** para el sistema de archivos del contenedor cuando sea posible

### Autenticación

- Usa **contraseñas fuertes** para todas las cuentas
- Implementa **rate limiting** para endpoints de autenticación (incluido por defecto)
- Monitorea logs de acceso para actividad sospechosa

### Red

- Despliega detrás de un **reverse proxy** (nginx, traefik)
- Usa **network policies** apropiadas en Kubernetes
- Restringe acceso a bases de datos a redes internas únicamente

## Características de Seguridad Incluidas

Cortex incluye varias características de seguridad por defecto:

- **Autenticación JWT** con tokens de corta duración
- **Rate limiting** para prevenir ataques de fuerza bruta
- **Detección y enmascaramiento de PII** (DNI, tarjetas, emails)
- **Headers de seguridad** (CORS, CSP, X-Frame-Options)
- **Logs de auditoría** para acciones sensibles
- **Contenedores no-root** en producción

## Contacto

Para preguntas relacionadas con seguridad que no sean reportes de vulnerabilidades, puedes contactarnos en:

**deeprat.tec@gmail.com** (Asunto: `[SECURITY-QUESTION] Tu pregunta`)

---

_Última actualización: Diciembre 2025_
