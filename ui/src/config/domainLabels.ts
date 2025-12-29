/**
 * Domain-specific labels and configurations for Cortex demos.
 *
 * Cortex is domain-agnostic. This configuration file enables customization
 * of UI labels for different demo scenarios without modifying core code.
 *
 * To switch domains, change the CORTEX_DEMO_DOMAIN environment variable:
 *   - "banking" (default)
 *   - "university"
 *   - "clinic" (future)
 */

// Read domain from environment or default to banking
const DEMO_DOMAIN = (import.meta.env.VITE_DEMO_DOMAIN || "banking") as
  | "banking"
  | "university"
  | "clinic";

// =============================================================================
// DOMAIN-SPECIFIC LABELS
// =============================================================================

interface DomainLabels {
  // Entity names
  subject: string;
  subjects: string;
  customer: string;
  customers: string;
  employee: string;
  employees: string;

  // Panel titles
  transactionalPanelTitle: string;
  transactionalPanelDescription: string;

  // Tab label (for navigation)
  transactionalTabLabel: string;

  // Product/Service names
  products: string;
  product: string;

  // Transaction names
  transactions: string;
  transaction: string;

  // Status messages
  loadingSubjects: string;
  noSubjectsFound: string;
  backToSubjects: string;

  // Service type groups (for the dropdown)
  serviceTypeGroups: Array<{
    group: string;
    types: Array<{ value: string; label: string }>;
  }>;

  // Transaction type groups
  transactionTypeGroups: Array<{
    group: string;
    types: Array<{ value: string; label: string }>;
  }>;
}

// =============================================================================
// BANKING DOMAIN (default)
// =============================================================================

const BANKING_LABELS: DomainLabels = {
  subject: "Cliente",
  subjects: "Clientes",
  customer: "Cliente",
  customers: "Clientes",
  employee: "Empleado",
  employees: "Empleados",

  transactionalPanelTitle: "Gestión Transaccional",
  transactionalPanelDescription:
    "Administre productos (cuentas, tarjetas, préstamos) y movimientos transaccionales de los clientes.",
  transactionalTabLabel: "Transaccional",

  products: "Productos",
  product: "Producto",
  transactions: "Movimientos",
  transaction: "Movimiento",

  loadingSubjects: "Cargando clientes...",
  noSubjectsFound: "No hay clientes registrados en el sistema.",
  backToSubjects: "← Volver a clientes",

  serviceTypeGroups: [
    {
      group: "Banca",
      types: [
        { value: "bank_account", label: "Cuenta Bancaria" },
        { value: "savings_account", label: "Cuenta de Ahorro" },
        { value: "credit_card", label: "Tarjeta de Crédito" },
        { value: "debit_card", label: "Tarjeta de Débito" },
        { value: "personal_loan", label: "Préstamo Personal" },
        { value: "mortgage", label: "Hipoteca" },
        { value: "credit_line", label: "Línea de Crédito" },
        { value: "fixed_term_deposit", label: "Plazo Fijo" },
        { value: "investment_fund", label: "Fondo de Inversión" },
      ],
    },
    {
      group: "Seguros",
      types: [
        { value: "life_insurance", label: "Seguro de Vida" },
        { value: "health_insurance", label: "Seguro de Salud" },
        { value: "auto_insurance", label: "Seguro de Automóvil" },
      ],
    },
  ],

  transactionTypeGroups: [
    {
      group: "Movimientos Financieros",
      types: [
        { value: "credit", label: "Ingreso / Crédito" },
        { value: "debit", label: "Cargo / Débito" },
        { value: "transfer_in", label: "Transferencia Recibida" },
        { value: "transfer_out", label: "Transferencia Enviada" },
        { value: "deposit", label: "Depósito" },
        { value: "withdrawal", label: "Retiro" },
      ],
    },
    {
      group: "Cargos y Comisiones",
      types: [
        { value: "fee", label: "Comisión" },
        { value: "service_charge", label: "Cargo por Servicio" },
        { value: "maintenance_fee", label: "Cuota de Mantenimiento" },
        { value: "penalty", label: "Penalización" },
      ],
    },
    {
      group: "Pagos",
      types: [
        { value: "payment", label: "Pago" },
        { value: "installment", label: "Cuota" },
        { value: "refund", label: "Reembolso" },
      ],
    },
  ],
};

// =============================================================================
// UNIVERSITY DOMAIN (FCE-IUC demo)
// =============================================================================

const UNIVERSITY_LABELS: DomainLabels = {
  subject: "Alumno",
  subjects: "Alumnos",
  customer: "Alumno",
  customers: "Alumnos",
  employee: "Docente/Personal",
  employees: "Docentes y Personal",

  transactionalPanelTitle: "Gestión Académica",
  transactionalPanelDescription:
    "Administre inscripciones, cursadas, notas y pagos de los alumnos.",
  transactionalTabLabel: "Académico",

  products: "Inscripciones",
  product: "Inscripción",
  transactions: "Movimientos Académicos",
  transaction: "Movimiento Académico",

  loadingSubjects: "Cargando alumnos...",
  noSubjectsFound: "No hay alumnos registrados en el sistema.",
  backToSubjects: "← Volver a alumnos",

  serviceTypeGroups: [
    {
      group: "Académico",
      types: [
        { value: "enrollment", label: "Matrícula (Inscripción a Carrera)" },
        {
          value: "course_registration",
          label: "Cursada (Inscripción a Materia)",
        },
        { value: "payment_plan", label: "Plan de Cuotas" },
        { value: "scholarship", label: "Beca" },
        { value: "extension_course", label: "Curso de Extensión" },
        { value: "postgraduate", label: "Posgrado" },
      ],
    },
    {
      group: "Servicios",
      types: [
        { value: "library_membership", label: "Membresía Biblioteca" },
        { value: "sports_membership", label: "Membresía Deportiva" },
        { value: "parking", label: "Estacionamiento" },
        { value: "locker", label: "Locker" },
      ],
    },
  ],

  transactionTypeGroups: [
    {
      group: "Evaluaciones",
      types: [
        { value: "grade", label: "Nota / Calificación" },
        { value: "attendance", label: "Asistencia" },
        { value: "homework", label: "Trabajo Práctico" },
        { value: "project", label: "Proyecto" },
        { value: "thesis_progress", label: "Avance de Tesis" },
      ],
    },
    {
      group: "Pagos",
      types: [
        { value: "tuition_payment", label: "Pago de Cuota" },
        { value: "enrollment_fee", label: "Matrícula" },
        { value: "exam_fee", label: "Arancel de Examen" },
        { value: "certificate_fee", label: "Arancel de Certificado" },
        { value: "late_fee", label: "Recargo por Mora" },
        { value: "refund", label: "Reembolso" },
      ],
    },
    {
      group: "Administrativo",
      types: [
        { value: "registration_change", label: "Cambio de Inscripción" },
        { value: "leave_of_absence", label: "Licencia" },
        { value: "reinstatement", label: "Reincorporación" },
        { value: "graduation", label: "Graduación" },
      ],
    },
  ],
};

// =============================================================================
// CLINIC DOMAIN (future)
// =============================================================================

const CLINIC_LABELS: DomainLabels = {
  subject: "Paciente",
  subjects: "Pacientes",
  customer: "Paciente",
  customers: "Pacientes",
  employee: "Personal Médico",
  employees: "Personal Médico",

  transactionalPanelTitle: "Gestión Clínica",
  transactionalPanelDescription:
    "Administre consultas, tratamientos, estudios y pagos de los pacientes.",
  transactionalTabLabel: "Clínico",

  products: "Servicios",
  product: "Servicio",
  transactions: "Movimientos Clínicos",
  transaction: "Movimiento Clínico",

  loadingSubjects: "Cargando pacientes...",
  noSubjectsFound: "No hay pacientes registrados en el sistema.",
  backToSubjects: "← Volver a pacientes",

  serviceTypeGroups: [
    {
      group: "Atención Médica",
      types: [
        { value: "consultation", label: "Consulta Médica" },
        { value: "treatment", label: "Tratamiento" },
        { value: "surgery", label: "Cirugía" },
        { value: "hospitalization", label: "Internación" },
      ],
    },
    {
      group: "Estudios",
      types: [
        { value: "lab_test", label: "Análisis de Laboratorio" },
        { value: "imaging", label: "Diagnóstico por Imágenes" },
        { value: "biopsy", label: "Biopsia" },
      ],
    },
  ],

  transactionTypeGroups: [
    {
      group: "Registros Médicos",
      types: [
        { value: "diagnosis", label: "Diagnóstico" },
        { value: "prescription", label: "Receta" },
        { value: "vital_signs", label: "Signos Vitales" },
        { value: "lab_result", label: "Resultado de Laboratorio" },
      ],
    },
    {
      group: "Pagos",
      types: [
        { value: "consultation_payment", label: "Pago de Consulta" },
        { value: "treatment_payment", label: "Pago de Tratamiento" },
        { value: "insurance_claim", label: "Reclamo a Obra Social" },
        { value: "refund", label: "Reembolso" },
      ],
    },
  ],
};

// =============================================================================
// DOMAIN SELECTION
// =============================================================================

const DOMAIN_CONFIGS: Record<string, DomainLabels> = {
  banking: BANKING_LABELS,
  university: UNIVERSITY_LABELS,
  clinic: CLINIC_LABELS,
};

/**
 * Get the current domain labels based on environment configuration.
 */
export function getDomainLabels(): DomainLabels {
  return DOMAIN_CONFIGS[DEMO_DOMAIN] || BANKING_LABELS;
}

/**
 * Get the current demo domain name.
 */
export function getCurrentDomain(): string {
  return DEMO_DOMAIN;
}

/**
 * Check if a specific domain is active.
 */
export function isDomain(domain: "banking" | "university" | "clinic"): boolean {
  return DEMO_DOMAIN === domain;
}

// Export the current labels for convenience
export const labels = getDomainLabels();

// Export types for consumers
export type { DomainLabels };

// =============================================================================
// DEMO CREDENTIALS CONFIGURATION
// =============================================================================

import type { DemoCredentialsPanelConfig } from "../modules/DemoCredentialsPanel";

/**
 * Demo mode types supported by the application.
 * - "none": No demo mode (production)
 * - "fce_iuc": FCE-IUC University demo with fixed credentials
 * - "firstrun": Clean demo with periodic reset
 */
export type DemoMode = "none" | "fce_iuc" | "firstrun" | "banking_demo";

/**
 * Get the current demo mode from environment.
 */
export function getDemoMode(): DemoMode {
  const mode = import.meta.env.VITE_DEMO_MODE as string | undefined;
  if (mode === "fce_iuc" || mode === "firstrun" || mode === "banking_demo") {
    return mode;
  }
  return "none";
}

/**
 * Check if demo credentials should be shown on login.
 */
export function shouldShowDemoCredentials(): boolean {
  const mode = getDemoMode();
  return mode === "fce_iuc" || mode === "banking_demo";
}

/**
 * Check if demo reset countdown should be shown.
 */
export function shouldShowDemoResetTimer(): boolean {
  return import.meta.env.VITE_DEMO_RESET_ENABLED === "true";
}

/**
 * Demo credentials configuration per mode.
 */
const DEMO_CREDENTIALS_CONFIG: Record<string, DemoCredentialsPanelConfig> = {
  fce_iuc: {
    title: "Credenciales de Demo",
    subtitle: "Usa estas credenciales para explorar el sistema",
    warningText: "ENTORNO DE DEMOSTRACIÓN - No ingreses datos reales",
    credentials: [
      {
        role: "Alumno",
        username: "alumno_alu-20210001",
        password: "Demo!ALU-20210001",
        description: "Estudiante de Contador Público",
      },
      {
        role: "Profesor",
        username: "prof.malvestiti",
        password: "Prof!Dan1el2025",
        description: "Docente de Contabilidad",
      },
      {
        role: "Admin",
        username: "admin.secretaria",
        password: "Admin!Secre2025",
        description: "Secretaría Académica",
      },
    ],
  },
  banking_demo: {
    title: "Demo Credentials",
    subtitle: "Use these credentials to explore the banking system",
    warningText: "DEMO ENVIRONMENT - Do not enter real data",
    credentials: [
      {
        role: "Customer",
        username: "demo_customer",
        password: "Demo!Customer2025",
        description: "Sample bank customer",
      },
      {
        role: "Employee",
        username: "demo_employee",
        password: "Demo!Employee2025",
        description: "Bank employee",
      },
      {
        role: "Admin",
        username: "admin_main",
        password: "admin123",
        description: "System administrator",
      },
    ],
  },
};

/**
 * Get demo credentials configuration for the current mode.
 * Returns null if no demo credentials should be shown.
 */
export function getDemoCredentialsConfig(): DemoCredentialsPanelConfig | null {
  const mode = getDemoMode();
  if (!shouldShowDemoCredentials()) {
    return null;
  }
  return DEMO_CREDENTIALS_CONFIG[mode] || null;
}
