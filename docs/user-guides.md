# Guías de Usuario por Rol

> Esta guía describe la experiencia de uso de Cortex para cada tipo de usuario.

Cortex implementa tres roles con diferentes niveles de acceso y funcionalidades:

| Rol          | Descripción                                                        | Acceso                      |
| ------------ | ------------------------------------------------------------------ | --------------------------- |
| **Customer** | Usuario final que consulta su información personal y documentación | Solo lectura                |
| **Employee** | Personal operativo que gestiona clientes y resuelve consultas      | Lectura + contexto múltiple |
| **Admin**    | Administrador del sistema con acceso completo                      | Control total               |

> **Nota sobre terminología**: Cortex es configurable para diferentes dominios. En despliegues educativos, Customer puede mostrarse como "Alumno" y Employee como "Profesor". En despliegues bancarios, Customer sería "Cliente" y Employee sería "Ejecutivo". La funcionalidad es idéntica; solo cambia la terminología visible.

---

## Primer Acceso al Sistema

### Instalación Nueva (First Run)

Cuando Cortex se despliega por primera vez, el sistema detecta que no existen usuarios y presenta un **wizard de bienvenida** que guía la creación del primer usuario administrador:

1. Pantalla de bienvenida con información del sistema
2. Formulario de creación del primer Admin (usuario, contraseña, email)
3. Confirmación y acceso al dashboard

Este administrador inicial puede luego crear usuarios adicionales desde el panel de gestión.

### Acceso Regular

Una vez configurado, la pantalla de login presenta:

- Campo de **Usuario**
- Campo de **Contraseña**
- Botón de acceso

No hay registro público; los usuarios son creados por administradores.

---

## Rol: Customer

El rol Customer está diseñado para usuarios finales que necesitan consultar su información personal y hacer preguntas sobre documentación disponible.

### Navegación

Tras iniciar sesión, el Customer ve una interfaz de dos columnas:

| Sección                | Ubicación         | Contenido                                                                 |
| ---------------------- | ----------------- | ------------------------------------------------------------------------- |
| **Resumen del Perfil** | Sidebar izquierda | Datos personales, productos/servicios activos, historial de transacciones |
| **Chat del Asistente** | Área principal    | Interfaz conversacional para consultas                                    |

No hay pestañas de navegación adicionales; toda la interacción se realiza desde esta vista unificada.

### Resumen del Perfil

Muestra información del cliente actual:

- **Identificador**: Código único del cliente (ej: CLI-20210001)
- **Datos de cuenta**: Tipo de cuenta, fecha de alta, estado
- **Productos activos**: Lista de productos/servicios con su estado (activo, completado, cancelado)
- **Transacciones recientes**: Historial de movimientos con fecha y monto

### Chat del Asistente

El área de chat permite hacer preguntas en lenguaje natural:

- **Campo de entrada**: "Haz una pregunta sobre tus datos o la documentación interna"
- **Sugerencias**: El sistema muestra ejemplos de consultas posibles
- **Respuestas**: Formato enriquecido con listas, notas y advertencias cuando aplica

**Comportamiento esperado**:

- La primera respuesta puede tardar ~10 segundos (inicialización del modelo)
- Las respuestas subsiguientes son más rápidas
- El botón cambia a "Generando..." durante el procesamiento

### Limitaciones del Rol

- Solo puede consultar su propia información
- No puede cambiar de contexto ni ver datos de otros usuarios
- Acceso de solo lectura

---

## Rol: Employee

El rol Employee está diseñado para personal operativo que necesita atender consultas de clientes y acceder a documentación interna.

### Navegación

La interfaz del Employee incluye:

| Elemento                 | Ubicación         | Función                                       |
| ------------------------ | ----------------- | --------------------------------------------- |
| **Selector de Contexto** | Header superior   | Dropdown para cambiar el contexto de consulta |
| **Cliente Activo**       | Sidebar izquierda | Información del cliente seleccionado          |
| **Resumen del Perfil**   | Sidebar izquierda | Datos detallados del cliente activo           |
| **Chat del Asistente**   | Área principal    | Consultas contextualizadas                    |

### Selector de Contexto

El dropdown de contexto agrupa las opciones en categorías:

1. **Documentación pública**: Información general accesible para todos
2. **Documentación interna**: Material restringido para personal
3. **Clientes**: Lista de clientes disponibles, identificados por nombre e ID

Al seleccionar un cliente, el chat responderá consultas sobre ese cliente específico.

### Panel de Cliente Activo

Cuando se selecciona un cliente, la sidebar muestra:

- **ID**: Identificador único
- **Nombre**: Nombre del cliente
- **Tipo**: Categoría (customer)
- **Estado**: Activo/Inactivo
- **Atributos adicionales**: Según configuración del dominio

### Chat Contextualizado

El chat funciona igual que para Customer, pero:

- Las respuestas pueden combinar información del cliente seleccionado con documentación
- El sistema indica la fuente de la información (perfil del cliente vs documentación)
- El badge de contexto en el header muestra el cliente activo

### Limitaciones del Rol

- Puede ver información de clientes pero no editarla
- No tiene acceso a paneles de administración
- No puede cargar documentos ni gestionar usuarios

---

## Rol: Admin

El rol Admin tiene acceso completo al sistema, incluyendo gestión de usuarios, datos y documentación.

### Navegación

La interfaz presenta cuatro pestañas principales:

| Pestaña        | Función                                    |
| -------------- | ------------------------------------------ |
| **Chat**       | Asistente con acceso a todos los contextos |
| **Usuarios**   | Gestión de usuarios del sistema            |
| **Datos**      | Gestión de registros y transacciones       |
| **Documentos** | Gestión del corpus RAG                     |

### Pestaña: Chat

Funciona igual que para Employee, con selector de contexto completo y acceso a toda la documentación y clientes.

### Pestaña: Usuarios

Dashboard de gestión de usuarios con:

**Métricas**:

- Total de usuarios
- Usuarios por tipo (Employee, Customer)
- Usuarios activos

**Acciones**:

- **Crear nuevo usuario**: Formulario para agregar usuarios

**Tabla de usuarios**:

| Columna  | Contenido                    |
| -------- | ---------------------------- |
| Usuario  | Nombre de usuario            |
| Tipo     | CUSTOMER / EMPLOYEE          |
| Rol      | Rol asignado en el sistema   |
| DLP      | Nivel de protección de datos |
| Estado   | ACTIVO / INACTIVO            |
| Acciones | Botones de acción            |

**Botones de acción**:

- **[E] Editar**: Edición en línea de rol, DLP y estado
- **[D] Detalles**: Modal con datos completos del usuario e historial de cambios
- **Eliminar**: Eliminar usuario del sistema

> **Nota**: El modal de edición de datos incluye un campo obligatorio para documentar el motivo del cambio, generando un audit trail.

### Pestaña: Datos

Gestión de registros de clientes:

**Tabla principal**:

| Columna     | Contenido                       |
| ----------- | ------------------------------- |
| ID          | Identificador del registro      |
| Subject Key | Clave del cliente (enlace)      |
| Nombre      | Nombre del cliente              |
| Tipo        | Categoría                       |
| Estado      | Estado actual                   |
| Productos   | Cantidad de productos/servicios |
| Acciones    | Ver productos, editar           |

**Vista de productos** (al hacer clic en un cliente):

- Lista de productos/servicios del cliente
- Estado de cada uno
- Fechas relevantes
- Acciones: Ver movimientos, Editar, Cerrar

**Vista de movimientos** (al hacer clic en un producto):

- Historial de transacciones
- Tipo, descripción, monto
- Saldo calculado
- Acciones: Editar, Eliminar

### Pestaña: Documentos

Gestión del corpus de documentos para el RAG:

**Subpestaña: Cargar Documentos**

- Área de drag & drop para archivos (PDF, TXT, MD hasta 50MB)
- Selector de categoría del documento
- Los documentos cargados se indexan automáticamente

**Subpestaña: Estado RAG**

- Estado de conexión con Qdrant
- Estado de la colección
- Cantidad de documentos indexados
- Botones: Actualizar Estado, Re-indexar Documentos

**Subpestaña: Historial**

- Registro de cargas e indexaciones
- Fecha, usuario, resultado

> **Nota técnica**: También es posible cargar documentos copiando archivos directamente en el directorio `./documentacion/publica/` del servidor y ejecutando una re-indexación.

---

## Elementos de Interfaz Comunes

### Indicadores de Estado

| Indicador      | Significado                  |
| -------------- | ---------------------------- |
| Badge verde    | Activo / Conectado / Exitoso |
| Badge rojo     | Inactivo / Error             |
| Badge amarillo | Pendiente / En proceso       |

### Acciones en Tablas

Los botones de acción en tablas usan iconografía compacta:

| Botón        | Acción                   |
| ------------ | ------------------------ |
| **[E]**      | Editar registro          |
| **[D]**      | Ver detalles / historial |
| **Eliminar** | Eliminar registro        |

> **Nota**: En versiones futuras, estos botones serán reemplazados por iconos estándar con tooltips descriptivos.

### Comportamiento del Chat

- **Primera consulta**: ~10 segundos de inicialización
- **Consultas subsiguientes**: Respuesta en 2-5 segundos
- **Indicador de carga**: Botón muestra "Generando..."
- **Formato de respuestas**: Markdown con listas, negritas, notas

---

## Configuración por Dominio

Cortex puede adaptarse a diferentes contextos de negocio mediante variables de entorno:

| Dominio         | Customer | Employee  | Contexto típico                               |
| --------------- | -------- | --------- | --------------------------------------------- |
| **Banca**       | Cliente  | Ejecutivo | Cuentas, transacciones, productos financieros |
| **Educación**   | Alumno   | Profesor  | Inscripciones, cursadas, calificaciones       |
| **Corporativo** | Usuario  | Operador  | Tickets, documentación, procesos              |

La funcionalidad del sistema es idéntica; solo cambian las etiquetas visibles en la interfaz.

---

<p align="center">
  <a href="getting-started.md">Inicio Rápido</a> |
  <a href="index.md">Índice</a>
</p>
