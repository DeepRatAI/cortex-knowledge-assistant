/**
 * UserManagement.tsx
 *
 * Full-screen user management module for administrators.
 *
 * Features:
 * - Full user CRUD operations
 * - Personal data editing with audit trail
 * - Role and permission management
 * - User activity monitoring
 * - Complete audit history per user
 *
 * Security considerations:
 * - Only accessible to admin role users
 * - All modifications are fully audited
 * - Password changes follow security policy
 * - Sensitive operations require confirmation
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  listUsers,
  updateUser,
  deleteUser,
  createUser,
  AdminUserInfo,
  UpdateUserRequest,
  CreateUserRequest,
  adminGetSubjectData,
  adminUpdateSubjectData,
  adminGetSubjectHistory,
  SubjectDataResponse,
  SubjectHistoryEntry,
} from "../services/api";
import {
  EditIcon,
  DataIcon,
  SuccessIcon,
  ErrorIcon,
  ICON_SIZES,
} from "../components/Icons";
import { useAuth } from "./AuthContext";
import { getDomainLabels } from "../config/domainLabels";

// Get labels at module load
const domainLabels = getDomainLabels();

// =============================================================================
// PASSWORD VALIDATION
// =============================================================================

const validatePassword = (
  password: string
): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];
  if (password.length < 8) {
    errors.push("Mínimo 8 caracteres");
  }
  if (!/[A-Z]/.test(password)) {
    errors.push("Al menos una mayúscula");
  }
  if (!/[a-z]/.test(password)) {
    errors.push("Al menos una minúscula");
  }
  if (!/[0-9]/.test(password)) {
    errors.push("Al menos un número");
  }
  return { valid: errors.length === 0, errors };
};

// =============================================================================
// USER ROW COMPONENT
// =============================================================================

interface UserRowProps {
  user: AdminUserInfo;
  onUpdate: () => void;
  onEditData: (subjectKey: string) => void;
}

const UserRow: React.FC<UserRowProps> = ({ user, onUpdate, onEditData }) => {
  const [editing, setEditing] = useState(false);
  const [editValues, setEditValues] = useState({
    display_name: user.display_name ?? "",
    role: user.role,
    dlp_level: user.dlp_level,
    is_active: user.is_active,
    can_access_all_subjects: user.can_access_all_subjects,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleSave = async () => {
    setLoading(true);
    setError(null);
    try {
      const updateReq: UpdateUserRequest = {
        display_name: editValues.display_name || undefined,
        role: editValues.role,
        dlp_level: editValues.dlp_level,
        is_active: editValues.is_active,
        can_access_all_subjects: editValues.can_access_all_subjects,
      };
      await updateUser(user.id, updateReq);
      setEditing(false);
      onUpdate();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al actualizar");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await deleteUser(user.id);
      onUpdate();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al eliminar");
    } finally {
      setLoading(false);
      setConfirmDelete(false);
    }
  };

  // Check if user has associated subject data (customers have subject_ids)
  const hasSubjectData =
    user.user_type === "customer" &&
    user.subject_ids &&
    user.subject_ids.length > 0;

  if (editing) {
    return (
      <tr className="user-row editing">
        <td>{user.username}</td>
        <td>{user.user_type}</td>
        <td>
          <select
            value={editValues.role}
            onChange={(e) =>
              setEditValues({ ...editValues, role: e.target.value })
            }
          >
            {user.user_type === "employee" ? (
              <>
                <option value="admin">Admin</option>
                <option value="support">Support</option>
                <option value="viewer">Viewer</option>
              </>
            ) : (
              <option value="customer">Customer</option>
            )}
          </select>
        </td>
        <td>
          <select
            value={editValues.dlp_level}
            onChange={(e) =>
              setEditValues({
                ...editValues,
                dlp_level: e.target.value as "standard" | "privileged",
              })
            }
          >
            <option value="standard">Standard</option>
            <option value="privileged">Privileged</option>
          </select>
        </td>
        <td>
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={editValues.is_active}
              onChange={(e) =>
                setEditValues({ ...editValues, is_active: e.target.checked })
              }
            />
            Activo
          </label>
        </td>
        <td className="user-actions">
          <button
            className="btn-small btn-save"
            onClick={handleSave}
            disabled={loading}
          >
            {loading ? "..." : "Guardar"}
          </button>
          <button
            className="btn-small btn-cancel"
            onClick={() => {
              setEditing(false);
              setError(null);
            }}
          >
            Cancelar
          </button>
          {error && <span className="inline-error">{error}</span>}
        </td>
      </tr>
    );
  }

  return (
    <tr className="user-row">
      <td>
        <strong>{user.username}</strong>
        {user.display_name && (
          <span className="user-display-name"> ({user.display_name})</span>
        )}
      </td>
      <td>
        <span className={`user-type-badge ${user.user_type}`}>
          {user.user_type}
        </span>
      </td>
      <td>
        <span
          className={`role-badge ${user.role}`}
          data-tooltip={
            user.role === "admin"
              ? "Acceso total: gestiona usuarios, documentos y configuracion"
              : user.role === "support"
              ? "Acceso a consultas y soporte de clientes"
              : user.role === "viewer"
              ? "Solo lectura: puede consultar pero no modificar"
              : "Cliente: acceso a sus propios datos"
          }
        >
          {user.role}
        </span>
      </td>
      <td>
        <span
          className={`dlp-badge ${user.dlp_level}`}
          data-tooltip={
            user.dlp_level === "privileged"
              ? "Acceso completo a datos sensibles sin enmascarar"
              : "Datos sensibles parcialmente enmascarados"
          }
        >
          {user.dlp_level}
        </span>
      </td>
      <td>
        <span
          className={`status-badge ${user.is_active ? "active" : "inactive"}`}
          data-tooltip={
            user.is_active
              ? "El usuario puede iniciar sesion y usar el sistema"
              : "Usuario bloqueado. No puede acceder al sistema"
          }
        >
          {user.is_active ? (
            <>
              <SuccessIcon size={ICON_SIZES.sm} /> Activo
            </>
          ) : (
            <>
              <ErrorIcon size={ICON_SIZES.sm} /> Inactivo
            </>
          )}
        </span>
      </td>
      <td className="user-actions">
        <button
          className="btn-icon btn-edit"
          onClick={() => setEditing(true)}
          data-tooltip="Editar permisos y configuracion"
          aria-label="Editar permisos y configuracion"
        >
          <EditIcon size={ICON_SIZES.md} />
        </button>
        {hasSubjectData && (
          <button
            className="btn-icon btn-data"
            onClick={() => onEditData(user.subject_ids![0])}
            data-tooltip="Ver y editar datos personales"
            aria-label="Ver y editar datos personales"
          >
            <DataIcon size={ICON_SIZES.md} />
          </button>
        )}
        {confirmDelete ? (
          <>
            <button
              className="btn-small btn-danger"
              onClick={handleDelete}
              disabled={loading}
            >
              {loading ? "..." : "Confirmar"}
            </button>
            <button
              className="btn-small btn-cancel"
              onClick={() => setConfirmDelete(false)}
            >
              No
            </button>
          </>
        ) : (
          <button
            className="btn-small btn-danger"
            onClick={handleDelete}
            title="Eliminar usuario"
          >
            Eliminar
          </button>
        )}
        {error && <span className="inline-error">{error}</span>}
      </td>
    </tr>
  );
};

// =============================================================================
// CREATE USER FORM
// =============================================================================

interface CreateUserFormProps {
  onUserCreated: () => void;
}

const CreateUserForm: React.FC<CreateUserFormProps> = ({ onUserCreated }) => {
  const [formData, setFormData] = useState<{
    username: string;
    password: string;
    confirmPassword: string;
    user_type: "customer" | "employee";
    role: string;
    display_name: string;
    dlp_level: "standard" | "privileged";
    can_access_all_subjects: boolean;
    subject_ids: string;
    full_name: string;
    document_id: string;
    tax_id: string;
    email: string;
    phone: string;
  }>({
    username: "",
    password: "",
    confirmPassword: "",
    user_type: "employee",
    role: "viewer",
    display_name: "",
    dlp_level: "standard",
    can_access_all_subjects: false,
    subject_ids: "",
    full_name: "",
    document_id: "",
    tax_id: "",
    email: "",
    phone: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const passwordValidation = validatePassword(formData.password);
  const passwordsMatch = formData.password === formData.confirmPassword;

  const roleOptions =
    formData.user_type === "employee"
      ? [
          { value: "admin", label: "Admin - Acceso total al sistema" },
          {
            value: "support",
            label: `Support - Atención al ${domainLabels.subject.toLowerCase()}`,
          },
          { value: "viewer", label: "Viewer - Solo lectura" },
        ]
      : [{ value: "customer", label: `Customer - ${domainLabels.subject}` }];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!formData.username.trim()) {
      setError("El nombre de usuario es requerido");
      return;
    }
    if (!passwordValidation.valid) {
      setError("La contraseña no cumple los requisitos de seguridad");
      return;
    }
    if (!passwordsMatch) {
      setError("Las contraseñas no coinciden");
      return;
    }

    const subjectIds =
      formData.user_type === "employee" && formData.subject_ids.trim()
        ? formData.subject_ids
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : undefined;

    setLoading(true);
    try {
      const request: CreateUserRequest = {
        username: formData.username.trim(),
        password: formData.password,
        user_type: formData.user_type,
        role: formData.user_type === "employee" ? formData.role : "customer",
        display_name: formData.display_name.trim() || undefined,
        dlp_level: formData.dlp_level,
        can_access_all_subjects:
          formData.user_type === "employee"
            ? formData.can_access_all_subjects
            : false,
        subject_ids: subjectIds,
        full_name: formData.full_name.trim() || undefined,
        document_id: formData.document_id.trim() || undefined,
        tax_id: formData.tax_id.trim() || undefined,
        email: formData.email.trim() || undefined,
        phone: formData.phone.trim() || undefined,
      };

      await createUser(request);
      setSuccess(`Usuario "${formData.username}" creado exitosamente`);
      setFormData({
        username: "",
        password: "",
        confirmPassword: "",
        user_type: "employee",
        role: "viewer",
        display_name: "",
        dlp_level: "standard",
        can_access_all_subjects: false,
        subject_ids: "",
        full_name: "",
        document_id: "",
        tax_id: "",
        email: "",
        phone: "",
      });
      onUserCreated();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al crear usuario");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="create-user-section">
      <button className="section-toggle" onClick={() => setExpanded(!expanded)}>
        {expanded ? "➖" : "➕"} Crear nuevo usuario
      </button>

      {expanded && (
        <form className="create-user-form" onSubmit={handleSubmit}>
          {error && <div className="form-error">{error}</div>}
          {success && <div className="form-success">{success}</div>}

          <div className="form-grid">
            {/* Column 1: Account Info */}
            <div className="form-column">
              <h4>Datos de Cuenta</h4>

              <div className="form-group">
                <label>Nombre de usuario *</label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) =>
                    setFormData({ ...formData, username: e.target.value })
                  }
                  placeholder="usuario123"
                  required
                />
              </div>

              <div className="form-group">
                <label>Contraseña *</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) =>
                    setFormData({ ...formData, password: e.target.value })
                  }
                  placeholder="••••••••"
                  required
                />
                {formData.password && !passwordValidation.valid && (
                  <ul className="password-requirements">
                    {passwordValidation.errors.map((err, i) => (
                      <li key={i} className="requirement-error">
                        {err}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="form-group">
                <label>Confirmar contraseña *</label>
                <input
                  type="password"
                  value={formData.confirmPassword}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      confirmPassword: e.target.value,
                    })
                  }
                  placeholder="••••••••"
                  required
                />
                {formData.confirmPassword && !passwordsMatch && (
                  <span className="field-error">
                    Las contraseñas no coinciden
                  </span>
                )}
              </div>

              <div className="form-group">
                <label>Tipo de usuario *</label>
                <select
                  value={formData.user_type}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      user_type: e.target.value as "customer" | "employee",
                      role:
                        e.target.value === "employee" ? "viewer" : "customer",
                    })
                  }
                >
                  <option value="employee">{domainLabels.employee}</option>
                  <option value="customer">{domainLabels.subject}</option>
                </select>
              </div>

              <div className="form-group">
                <label>Rol *</label>
                <select
                  value={formData.role}
                  onChange={(e) =>
                    setFormData({ ...formData, role: e.target.value })
                  }
                >
                  {roleOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Column 2: Personal Info */}
            <div className="form-column">
              <h4>Datos Personales</h4>

              <div className="form-group">
                <label>Nombre para mostrar</label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) =>
                    setFormData({ ...formData, display_name: e.target.value })
                  }
                  placeholder="Juan Pérez"
                />
              </div>

              <div className="form-group">
                <label>Nombre completo</label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) =>
                    setFormData({ ...formData, full_name: e.target.value })
                  }
                  placeholder="Juan Carlos Pérez García"
                />
              </div>

              <div className="form-group">
                <label>DNI / Documento</label>
                <input
                  type="text"
                  value={formData.document_id}
                  onChange={(e) =>
                    setFormData({ ...formData, document_id: e.target.value })
                  }
                  placeholder="12345678"
                />
              </div>

              <div className="form-group">
                <label>CUIL / CUIT</label>
                <input
                  type="text"
                  value={formData.tax_id}
                  onChange={(e) =>
                    setFormData({ ...formData, tax_id: e.target.value })
                  }
                  placeholder="20-12345678-9"
                />
              </div>

              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  placeholder="usuario@email.com"
                />
              </div>

              <div className="form-group">
                <label>Teléfono</label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) =>
                    setFormData({ ...formData, phone: e.target.value })
                  }
                  placeholder="+54 11 1234-5678"
                />
              </div>
            </div>

            {/* Column 3: Permissions (only for employees) */}
            {formData.user_type === "employee" && (
              <div className="form-column">
                <h4>Permisos</h4>

                <div className="form-group">
                  <label>Nivel DLP</label>
                  <select
                    value={formData.dlp_level}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        dlp_level: e.target.value as "standard" | "privileged",
                      })
                    }
                  >
                    <option value="standard">
                      Standard - Datos redactados
                    </option>
                    <option value="privileged">
                      Privileged - Datos visibles
                    </option>
                  </select>
                </div>

                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={formData.can_access_all_subjects}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          can_access_all_subjects: e.target.checked,
                        })
                      }
                    />
                    Acceso a todos los {domainLabels.subjects.toLowerCase()}
                  </label>
                </div>

                {!formData.can_access_all_subjects && (
                  <div className="form-group">
                    <label>Subject IDs permitidos</label>
                    <input
                      type="text"
                      value={formData.subject_ids}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          subject_ids: e.target.value,
                        })
                      }
                      placeholder="CLI-00001, CLI-00002"
                    />
                    <small>Separados por comas</small>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="form-actions">
            <button
              type="submit"
              className="btn-primary"
              disabled={loading || !passwordValidation.valid || !passwordsMatch}
            >
              {loading ? "Creando..." : "Crear Usuario"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setExpanded(false)}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
    </div>
  );
};

// =============================================================================
// SUBJECT DATA EDITOR (Personal Data with Audit)
// =============================================================================

interface SubjectDataEditorProps {
  subjectKey: string;
  onClose: () => void;
  onSaved: () => void;
}

const SubjectDataEditor: React.FC<SubjectDataEditorProps> = ({
  subjectKey,
  onClose,
  onSaved,
}) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [data, setData] = useState<SubjectDataResponse | null>(null);
  const [history, setHistory] = useState<SubjectHistoryEntry[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const [formData, setFormData] = useState({
    display_name: "",
    full_name: "",
    document_id: "",
    tax_id: "",
    email: "",
    phone: "",
    change_reason: "",
  });

  useEffect(() => {
    loadData();
  }, [subjectKey]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const subjectData = await adminGetSubjectData(subjectKey);
      setData(subjectData);
      setFormData({
        display_name: subjectData.display_name || "",
        full_name: subjectData.full_name || "",
        document_id: subjectData.document_id || "",
        tax_id: subjectData.tax_id || "",
        email: subjectData.email || "",
        phone: subjectData.phone || "",
        change_reason: "",
      });
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al cargar datos");
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    try {
      const historyData = await adminGetSubjectHistory(subjectKey);
      setHistory(historyData);
      setShowHistory(true);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al cargar historial");
    }
  };

  const handleSave = async () => {
    if (!formData.change_reason.trim()) {
      setError("Debe indicar el motivo del cambio (requerido para auditoría)");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await adminUpdateSubjectData(subjectKey, {
        display_name: formData.display_name || undefined,
        full_name: formData.full_name || undefined,
        document_id: formData.document_id || undefined,
        tax_id: formData.tax_id || undefined,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        reason: formData.change_reason,
      });
      setSuccess("Datos actualizados correctamente");
      setFormData({ ...formData, change_reason: "" });
      onSaved();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="subject-editor-modal">
        <div className="modal-content">
          <div className="loading-spinner">Cargando datos...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="subject-editor-modal">
      <div className="modal-content large">
        <div className="modal-header">
          <h3>Editar Datos del {domainLabels.subject}</h3>
          <span className="subject-key">{subjectKey}</span>
          <button className="btn-close" onClick={onClose}>
            ✕
          </button>
        </div>

        {error && <div className="form-error">{error}</div>}
        {success && <div className="form-success">{success}</div>}

        <div className="modal-body">
          <div className="editor-grid">
            <div className="form-group">
              <label>Nombre para mostrar</label>
              <input
                type="text"
                value={formData.display_name}
                onChange={(e) =>
                  setFormData({ ...formData, display_name: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label>Nombre completo</label>
              <input
                type="text"
                value={formData.full_name}
                onChange={(e) =>
                  setFormData({ ...formData, full_name: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label>DNI / Documento</label>
              <input
                type="text"
                value={formData.document_id}
                onChange={(e) =>
                  setFormData({ ...formData, document_id: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label>CUIL / CUIT</label>
              <input
                type="text"
                value={formData.tax_id}
                onChange={(e) =>
                  setFormData({ ...formData, tax_id: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label>Teléfono</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) =>
                  setFormData({ ...formData, phone: e.target.value })
                }
              />
            </div>
          </div>

          <div className="form-group full-width">
            <label>Motivo del cambio * (obligatorio para auditoría)</label>
            <textarea
              value={formData.change_reason}
              onChange={(e) =>
                setFormData({ ...formData, change_reason: e.target.value })
              }
              placeholder={`Ej: Corrección de datos según solicitud del ${domainLabels.subject.toLowerCase()} vía ticket #12345`}
              rows={2}
            />
          </div>

          {/* History section */}
          <div className="history-section">
            <button
              className="btn-secondary"
              onClick={showHistory ? () => setShowHistory(false) : loadHistory}
            >
              {showHistory ? "Ocultar historial" : "Ver historial de cambios"}
            </button>

            {showHistory && history.length > 0 && (
              <div className="history-list">
                <h4>Historial de Modificaciones</h4>
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Operador</th>
                      <th>Motivo</th>
                      <th>Cambios</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((entry, i) => (
                      <tr key={i}>
                        <td>{new Date(entry.timestamp).toLocaleString()}</td>
                        <td>
                          {entry.operator_username ||
                            `ID: ${entry.operator_user_id}`}
                        </td>
                        <td>{entry.change_reason}</td>
                        <td>
                          <details>
                            <summary>Ver detalles</summary>
                            <pre className="change-details">
                              {JSON.stringify(entry.fields_changed, null, 2)}
                            </pre>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {showHistory && history.length === 0 && (
              <p className="no-history">No hay historial de modificaciones</p>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving || !formData.change_reason.trim()}
          >
            {saving ? "Guardando..." : "Guardar Cambios"}
          </button>
          <button className="btn-secondary" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// MAIN USER MANAGEMENT COMPONENT
// =============================================================================

interface UserManagementProps {
  onSubjectsChanged?: () => void;
}

export const UserManagement: React.FC<UserManagementProps> = ({
  onSubjectsChanged,
}) => {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "employee" | "customer">("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [editingSubject, setEditingSubject] = useState<string | null>(null);

  const isAdmin = user?.user_type === "employee" && user?.role === "admin";

  const loadUsers = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    try {
      const data = await listUsers();
      setUsers(data);
      setError(null);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al cargar usuarios");
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleUserCreated = () => {
    loadUsers();
    onSubjectsChanged?.();
  };

  const handleSubjectSaved = () => {
    loadUsers();
    onSubjectsChanged?.();
  };

  if (!isAdmin) {
    return (
      <div className="access-denied">
        <h2>Acceso Denegado</h2>
        <p>Solo los administradores pueden acceder a la gestión de usuarios.</p>
      </div>
    );
  }

  const filteredUsers = users.filter((u) => {
    const matchesFilter = filter === "all" || u.user_type === filter;
    const matchesSearch =
      !searchTerm ||
      u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (u.display_name?.toLowerCase().includes(searchTerm.toLowerCase()) ??
        false);
    return matchesFilter && matchesSearch;
  });

  const stats = {
    total: users.length,
    employees: users.filter((u) => u.user_type === "employee").length,
    customers: users.filter((u) => u.user_type === "customer").length,
    active: users.filter((u) => u.is_active).length,
  };

  return (
    <div className="user-management-page">
      <header className="page-header">
        <h2>Gestión de Usuarios</h2>
        <p className="page-description">
          Administración completa de usuarios, roles y permisos del sistema.
        </p>
      </header>

      {/* Stats cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-value">{stats.total}</span>
          <span className="stat-label">Total Usuarios</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.employees}</span>
          <span className="stat-label">{domainLabels.employees}</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.customers}</span>
          <span className="stat-label">{domainLabels.subjects}</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.active}</span>
          <span className="stat-label">Activos</span>
        </div>
      </div>

      {/* Create user form */}
      <CreateUserForm onUserCreated={handleUserCreated} />

      {/* Filters */}
      <div className="filters-bar">
        <div className="filter-group">
          <label>Filtrar por tipo:</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
          >
            <option value="all">Todos</option>
            <option value="employee">{domainLabels.employees}</option>
            <option value="customer">{domainLabels.subjects}</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Buscar:</label>
          <input
            type="text"
            placeholder="Nombre o usuario..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <button className="btn-refresh" onClick={loadUsers} disabled={loading}>
          {loading ? "..." : "Actualizar"}
        </button>
      </div>

      {/* Error display */}
      {error && <div className="page-error">{error}</div>}

      {/* Users table */}
      <div className="users-table-container">
        {loading ? (
          <div className="loading-state">Cargando usuarios...</div>
        ) : filteredUsers.length === 0 ? (
          <div className="empty-state">
            No se encontraron usuarios con los filtros actuales.
          </div>
        ) : (
          <table className="users-table">
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Tipo</th>
                <th>Rol</th>
                <th>DLP</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <UserRow
                  key={u.id}
                  user={u}
                  onUpdate={loadUsers}
                  onEditData={setEditingSubject}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Subject data editor modal */}
      {editingSubject && (
        <SubjectDataEditor
          subjectKey={editingSubject}
          onClose={() => setEditingSubject(null)}
          onSaved={handleSubjectSaved}
        />
      )}
    </div>
  );
};

export default UserManagement;
