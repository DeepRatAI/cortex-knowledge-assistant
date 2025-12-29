import React, { useState } from "react";
import {
  createInitialAdmin,
  CreateAdminRequest,
  SystemStatus,
} from "../services/api";

interface SetupWizardProps {
  systemStatus: SystemStatus;
  onSetupComplete: () => void;
}

type SetupStep = "welcome" | "create-admin" | "success";

export const SetupWizard: React.FC<SetupWizardProps> = ({
  systemStatus,
  onSetupComplete,
}) => {
  const [step, setStep] = useState<SetupStep>("welcome");
  const [formData, setFormData] = useState<CreateAdminRequest>({
    username: "",
    password: "",
    display_name: "",
  });
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    if (name === "confirmPassword") {
      setConfirmPassword(value);
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }));
    }
    setError(null);
  };

  const validateForm = (): boolean => {
    if (!formData.username.trim()) {
      setError("El nombre de usuario es obligatorio");
      return false;
    }
    if (formData.username.length < 3) {
      setError("El nombre de usuario debe tener al menos 3 caracteres");
      return false;
    }
    if (!formData.password) {
      setError("La contraseña es obligatoria");
      return false;
    }
    if (formData.password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres");
      return false;
    }
    if (!/[a-z]/.test(formData.password)) {
      setError("La contraseña debe contener al menos una letra minúscula");
      return false;
    }
    if (!/[A-Z]/.test(formData.password)) {
      setError("La contraseña debe contener al menos una letra mayúscula");
      return false;
    }
    if (!/\d/.test(formData.password)) {
      setError("La contraseña debe contener al menos un número");
      return false;
    }
    if (!/[@$!%*?&_\-]/.test(formData.password)) {
      setError(
        "La contraseña debe contener al menos un carácter especial (@$!%*?&_-)"
      );
      return false;
    }
    if (formData.password !== confirmPassword) {
      setError("Las contraseñas no coinciden");
      return false;
    }
    return true;
  };

  const handleCreateAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    setError(null);

    try {
      await createInitialAdmin({
        username: formData.username.trim().toLowerCase(),
        password: formData.password,
        display_name: formData.display_name?.trim() || formData.username.trim(),
      });
      setStep("success");
    } catch (err: any) {
      setError(err?.message || "Error al crear el usuario administrador");
    } finally {
      setLoading(false);
    }
  };

  const renderWelcome = () => (
    <div className="setup-step">
      <div className="setup-icon">[C]</div>
      <h2>Bienvenido a Cortex</h2>
      <p className="setup-description">
        <strong>Cortex</strong> es una plataforma de asistencia AI con
        implementación avanzada de ciberseguridad (DLP, PII, Multi-tenant, JWT).
      </p>
      <div className="setup-features">
        <div className="setup-feature">
          <span className="feature-icon">[S]</span>
          <span>Seguridad de nivel empresarial</span>
        </div>
        <div className="setup-feature">
          <span className="feature-icon">AI</span>
          <span>RAG + LLM integrado</span>
        </div>
        <div className="setup-feature">
          <span className="feature-icon">*</span>
          <span>Auditable y rastreable</span>
        </div>
        <div className="setup-feature">
          <span className="feature-icon">@</span>
          <span>Agnóstico de dominio</span>
        </div>
      </div>
      <p className="setup-note">
        Esta es la primera vez que se ejecuta Cortex. Necesitas crear una cuenta
        de administrador para comenzar.
      </p>
      <button
        className="setup-button primary"
        onClick={() => setStep("create-admin")}
      >
        Comenzar configuración
      </button>
    </div>
  );

  const renderCreateAdmin = () => (
    <div className="setup-step">
      <h2>Crear cuenta de administrador</h2>
      <p className="setup-description">
        Esta será la cuenta principal con acceso completo al sistema. Guarda
        estas credenciales en un lugar seguro.
      </p>
      <form className="setup-form" onSubmit={handleCreateAdmin}>
        <label>
          Nombre de usuario
          <input
            type="text"
            name="username"
            value={formData.username}
            onChange={handleInputChange}
            placeholder="ej: admin.principal"
            autoComplete="username"
            disabled={loading}
          />
          <span className="input-hint">
            Solo letras, números, puntos y guiones
          </span>
        </label>
        <label>
          Nombre para mostrar (opcional)
          <input
            type="text"
            name="display_name"
            value={formData.display_name}
            onChange={handleInputChange}
            placeholder="ej: Administrador Principal"
            disabled={loading}
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            name="password"
            value={formData.password}
            onChange={handleInputChange}
            placeholder="Mínimo 8 caracteres"
            autoComplete="new-password"
            disabled={loading}
          />
          <span className="input-hint">
            Debe incluir: mayúscula, minúscula, número y símbolo (@$!%*?&_-)
          </span>
        </label>
        <label>
          Confirmar contraseña
          <input
            type="password"
            name="confirmPassword"
            value={confirmPassword}
            onChange={handleInputChange}
            placeholder="Repite la contraseña"
            autoComplete="new-password"
            disabled={loading}
          />
        </label>
        {error && <div className="setup-error">{error}</div>}
        <div className="setup-actions">
          <button
            type="button"
            className="setup-button secondary"
            onClick={() => setStep("welcome")}
            disabled={loading}
          >
            Atrás
          </button>
          <button
            type="submit"
            className="setup-button primary"
            disabled={loading}
          >
            {loading ? "Creando..." : "Crear administrador"}
          </button>
        </div>
      </form>
    </div>
  );

  const renderSuccess = () => (
    <div className="setup-step">
      <div className="setup-icon success">✓</div>
      <h2>¡Configuración completada!</h2>
      <p className="setup-description">
        El usuario administrador <strong>{formData.username}</strong> ha sido
        creado exitosamente. Ahora puedes iniciar sesión para:
      </p>
      <ul className="setup-next-steps">
        <li>Cargar documentos para el asistente RAG</li>
        <li>Crear usuarios adicionales (empleados y clientes)</li>
        <li>Configurar el sistema según tus necesidades</li>
      </ul>
      <button className="setup-button primary" onClick={onSetupComplete}>
        Ir al inicio de sesión
      </button>
    </div>
  );

  return (
    <div className="setup-wizard">
      <div className="setup-container">
        <div className="setup-header">
          <h1>Cortex</h1>
          <span className="setup-badge">Configuración inicial</span>
        </div>
        <div className="setup-progress">
          <div
            className={`progress-step ${
              step === "welcome" ? "active" : "completed"
            }`}
          >
            <span className="step-number">1</span>
            <span className="step-label">Bienvenida</span>
          </div>
          <div
            className={`progress-step ${
              step === "create-admin"
                ? "active"
                : step === "success"
                ? "completed"
                : ""
            }`}
          >
            <span className="step-number">2</span>
            <span className="step-label">Crear Admin</span>
          </div>
          <div
            className={`progress-step ${
              step === "success" ? "active completed" : ""
            }`}
          >
            <span className="step-number">3</span>
            <span className="step-label">Listo</span>
          </div>
        </div>
        <div className="setup-content">
          {step === "welcome" && renderWelcome()}
          {step === "create-admin" && renderCreateAdmin()}
          {step === "success" && renderSuccess()}
        </div>
        <div className="setup-footer">
          <p>
            Estado del sistema: Qdrant{" "}
            {systemStatus.qdrant.reachable ? "✓" : "✗"} | LLM:{" "}
            {systemStatus.llm.provider.toUpperCase()}{" "}
            {systemStatus.llm.healthy ? "✓" : "✗"}
          </p>
        </div>
      </div>
    </div>
  );
};
