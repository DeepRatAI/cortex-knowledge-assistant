# Roadmap

> Última actualización: 28 Diciembre 2025

---

## Design Intent

La versión 1.0.0 prioriza **estabilidad operativa y experiencia de usuario** sobre expansión funcional. El objetivo es consolidar Cortex como un sistema confiable en producción antes de introducir capacidades avanzadas.

**Principios rectores:**

- Cada rol (Customer, Employee, Admin) debe poder operar de forma autónoma con su superficie funcional
- La UX debe ser autoexplicativa; el sistema no debe requerir capacitación para uso básico
- Las operaciones destructivas requieren confirmación explícita
- El RAG debe ser transparente sobre sus fuentes y limitaciones

**Fuera de alcance para v1.0.0:**

- Integraciones con sistemas externos (ERP, CRM, core bancario)
- Capacidades offline o PWA
- Internacionalización (i18n)
- Marketplace de plugins o extensiones

---

## Estado Actual: Beta

La versión Beta incluye:

- Core RAG con recuperación híbrida (semántica + keyword + topic scoring)
- Sistema multi-tenant con aislamiento de datos por cliente
- Detección y enmascaramiento de PII (DNI, tarjetas, emails, teléfonos)
- Streaming de respuestas en tiempo real via SSE
- Autenticación JWT con RBAC (Admin, Employee, Customer)
- Métricas Prometheus y health checks
- Manifests Kubernetes production-ready
- Documentación completa

---

## Próxima Versión: v1.0.0

La versión 1.0.0 expande las capacidades del sistema para cada tipo de usuario, manteniendo el aislamiento de datos y la trazabilidad como invariantes.

### Domain: Customer Experience

Visibilidad operacional y autonomía para usuarios finales. El cliente puede consultar su información sin intervención del staff.

| Feature                      | Descripción                                                 | Status  | Prioridad |
| ---------------------------- | ----------------------------------------------------------- | ------- | --------- |
| Transaction & Product Viewer | Panel self-service para consulta de movimientos y productos | Planned | Alta      |
| Direct Communication System  | Canal de mensajería seguro con personal de soporte          | Planned | Alta      |
| Account Settings Panel       | Preferencias, notificaciones y gestión de perfil            | Planned | Media     |

### Domain: Employee Productivity

Herramientas para operación eficiente del personal. El empleado puede gestionar clientes y resolver casos sin escalar innecesariamente.

| Feature            | Descripción                                      | Status    | Prioridad |
| ------------------ | ------------------------------------------------ | --------- | --------- |
| Customer Lookup    | Búsqueda y visualización de perfiles e historial | Planned   | Alta      |
| Limited CRUD       | Edición de datos con scope por rol y audit trail | Planned   | Alta      |
| Internal Ticketing | Gestión de tareas y escalamiento con admins      | Planned   | Alta      |
| Internal Chat      | Comunicación en tiempo real con administradores  | Planned   | Media     |
| Agentic LLM        | Automatización de tareas y soporte de decisiones | Exploring | Media     |
| Document Viewer    | Preview de documentos in-app                     | Planned   | Baja      |

### Domain: Admin Operations

Control y gobernanza del sistema. El administrador tiene visibilidad completa y puede delegar, auditar y configurar.

| Feature                 | Descripción                                  | Status    | Prioridad |
| ----------------------- | -------------------------------------------- | --------- | --------- |
| Pending Tasks Dashboard | Asignación, tracking y delegación de tareas  | Planned   | Alta      |
| Internal Ticketing      | Gestión unificada de workflows del staff     | Planned   | Alta      |
| Internal Chat           | Comunicación en tiempo real del equipo       | Planned   | Media     |
| Agentic LLM             | Automatización avanzada para tareas admin    | Exploring | Media     |
| Document Viewer         | Gestión y preview centralizado de documentos | Planned   | Baja      |

---

### Cross-Cutting: UX & Polish

Mejoras transversales de experiencia de usuario identificadas durante testing de la beta.

#### UI/UX General

| Mejora                                | Descripción                                      | Status    | Prioridad |
| ------------------------------------- | ------------------------------------------------ | --------- | --------- |
| Tooltips en acciones                  | Tooltips descriptivos en botones iconográficos   | ✅ Done   | Alta      |
| Iconografía estándar                  | Iconos SVG (Lucide) en lugar de emojis/letras    | ✅ Done   | Media     |
| Confirmación de acciones destructivas | Modal para eliminar, reindexar o modificar datos | Planned   | Alta      |
| Manejo de errores frontend            | Mensajes amigables en lugar de JSON/traces       | Planned   | Alta      |
| Onboarding opcional                   | Mini tour o panel "¿Qué puedo hacer aquí?"       | Exploring | Baja      |

#### Chat & RAG UX

| Mejora                      | Descripción                                         | Status  | Prioridad |
| --------------------------- | --------------------------------------------------- | ------- | --------- |
| Indicador de inicialización | Mensaje durante cold start del LLM (~10s)           | ✅ Done | Alta      |
| Badge de contexto activo    | Indicador visual del contexto seleccionado          | ✅ Done | Alta      |
| Explicación del selector    | Texto explicando qué filtra cada opción             | ✅ Done | Media     |
| Atribución de fuentes       | Indicar origen de la respuesta (docs, perfil, etc.) | Planned | Media     |

#### Data Management UX

| Mejora                    | Descripción                                      | Status  | Prioridad |
| ------------------------- | ------------------------------------------------ | ------- | --------- |
| Estados con semántica     | Tooltips explicando consecuencias de cada estado | ✅ Done | Media     |
| Empty states informativos | Mensajes contextuales cuando no hay datos        | ✅ Done | Media     |

---

## Definiciones

### Status

| Status        | Significado                                    |
| ------------- | ---------------------------------------------- |
| **✅ Done**   | Implementado y desplegado                      |
| **Planned**   | Definido y listo para implementación           |
| **In Design** | En proceso de diseño, especificación pendiente |
| **Exploring** | Bajo consideración, requiere validación        |

### Prioridad

| Prioridad | Criterio                                                 |
| --------- | -------------------------------------------------------- |
| **Alta**  | Requerido para operación segura y predecible del sistema |
| **Media** | Mejora significativa de productividad o experiencia      |
| **Baja**  | Deseable, puede diferirse a releases posteriores         |

---

## Notas

- Los tres dominios (Customer, Employee, Admin) se implementarán como parte de v1.0.0
- Las mejoras Cross-Cutting se aplicarán en paralelo durante el desarrollo
- Items con status `Exploring` podrían moverse a v1.1.0 según validación
- Este roadmap se actualizará según feedback de usuarios y stakeholders

---

<p align="center">
  <a href="development.md">Desarrollo</a> |
  <a href="index.md">Índice</a>
</p>
