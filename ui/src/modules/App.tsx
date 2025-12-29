import React, { useEffect, useMemo, useState } from "react";
import { Chat, ChatMessage } from "./Chat";
import { SidePanel } from "./SidePanel";
import { Login } from "./Login";
import { SetupWizard } from "./SetupWizard";
import { TransactionalPanel } from "./TransactionalPanel";
import { UserManagement } from "./UserManagement";
import { DocumentManagement } from "./DocumentManagement";
import { DemoResetCountdown } from "./DemoResetCountdown";
import { useAuth } from "./AuthContext";
import {
  listSubjects,
  SubjectSummary,
  getSystemStatus,
  SystemStatus,
} from "../services/api";
import {
  getDomainLabels,
  shouldShowDemoResetTimer,
} from "../config/domainLabels";
import {
  DocumentIcon,
  EducationalIcon,
  UserIcon,
  ICON_SIZES,
} from "../components/Icons";
import "../styles.css";

// Get labels at module load
const domainLabels = getDomainLabels();
const showResetTimer = shouldShowDemoResetTimer();

type AppState = "loading" | "setup" | "login" | "authenticated";
type MainView = "chat" | "users" | "transactional" | "documents";
// Context type for document filtering
type ContextType = "public_docs" | "educational" | null;

export const App: React.FC = () => {
  const { token, user, logout } = useAuth();
  const [appState, setAppState] = useState<AppState>("loading");
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    null
  );
  // Context type for filtering documents (public_docs, educational, or null for user-specific)
  const [contextType, setContextType] = useState<ContextType>("public_docs");
  const [subjects, setSubjects] = useState<SubjectSummary[] | null>(null);
  const [subjectsError, setSubjectsError] = useState<string | null>(null);
  const [mainView, setMainView] = useState<MainView>("chat");

  // Chat messages state - persisted at App level to survive tab switches
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  /**
   * Secure logout handler - clears chat history before logging out
   * to prevent session data leakage between users.
   * Security: Ensures no PII or context from previous session persists.
   */
  const handleSecureLogout = () => {
    setChatMessages([]);
    setSelectedSubjectId(null);
    setContextType("public_docs");
    logout();
  };

  // Check system status on mount
  useEffect(() => {
    let cancelled = false;
    const checkSystem = async () => {
      try {
        const status = await getSystemStatus();
        if (cancelled) return;
        setSystemStatus(status);

        if (status.system.first_run) {
          setAppState("setup");
        } else if (token && user) {
          setAppState("authenticated");
        } else {
          setAppState("login");
        }
      } catch (error) {
        console.error("Failed to check system status:", error);
        if (cancelled) return;
        if (token && user) {
          setAppState("authenticated");
        } else {
          setAppState("login");
        }
      }
    };
    checkSystem();
    return () => {
      cancelled = true;
    };
  }, []);

  // Update app state when auth changes
  useEffect(() => {
    if (appState === "loading") return;
    if (appState === "setup") return;

    if (token && user) {
      setAppState("authenticated");
    } else {
      setAppState("login");
    }
  }, [token, user, appState]);

  // Function to refresh subjects list (exposed to child components)
  const refreshSubjects = async () => {
    if (!token || !user || user.user_type !== "employee") {
      return;
    }
    try {
      const data = await listSubjects();
      setSubjects(data);
      setSubjectsError(null);
    } catch (e: any) {
      setSubjectsError(
        e?.message ||
          `No se pudo cargar la lista de ${domainLabels.subjects.toLowerCase()}.`
      );
    }
  };

  // Load subjects for employees
  useEffect(() => {
    if (!token || !user || user.user_type !== "employee") {
      setSubjects(null);
      setSelectedSubjectId(null);
      return;
    }
    let cancelled = false;
    setSubjectsError(null);
    void (async () => {
      try {
        const data = await listSubjects();
        if (!cancelled) {
          setSubjects(data);
          if (
            !selectedSubjectId &&
            data.length > 0 &&
            !user.can_access_all_subjects
          ) {
            setSelectedSubjectId(data[0].subject_id);
          }
        }
      } catch (e: any) {
        if (!cancelled) {
          setSubjectsError(
            e?.message ||
              `No se pudo cargar la lista de ${domainLabels.subjects.toLowerCase()}.`
          );
          setSubjects(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, user]);

  const handleSetupComplete = () => {
    setAppState("login");
  };

  // Handle context selection change
  const handleContextChange = (value: string) => {
    if (value === "public_docs") {
      setContextType("public_docs");
      setSelectedSubjectId(null);
    } else if (value === "educational") {
      setContextType("educational");
      setSelectedSubjectId(null);
    } else {
      // It's a subject ID
      setContextType(null);
      setSelectedSubjectId(value);
    }
  };

  // Get current selector value
  const getCurrentSelectorValue = (): string => {
    if (contextType === "public_docs") return "public_docs";
    if (contextType === "educational") return "educational";
    return selectedSubjectId ?? "public_docs";
  };

  // Get context badge info based on current selection
  const getContextBadge = () => {
    if (contextType === "public_docs") {
      return {
        icon: <DocumentIcon size={ICON_SIZES.sm} />,
        label: "Docs",
        className: "context-docs",
      };
    }
    if (contextType === "educational") {
      return {
        icon: <EducationalIcon size={ICON_SIZES.sm} />,
        label: "Educativo",
        className: "context-educational",
      };
    }
    if (selectedSubjectId) {
      const subject = subjects?.find((s) => s.subject_id === selectedSubjectId);
      const name = subject?.display_name || selectedSubjectId;
      return {
        icon: <UserIcon size={ICON_SIZES.sm} />,
        label: name,
        className: "context-subject",
      };
    }
    return null;
  };

  // Get helper text for selector
  const getSelectorHelperText = (): string => {
    if (contextType === "public_docs") {
      return "El asistente responderá usando documentación pública del sistema.";
    }
    if (contextType === "educational") {
      return "El asistente usará material educativo y guías de estudio.";
    }
    if (selectedSubjectId) {
      return "El asistente tiene acceso al perfil y datos de este usuario específico.";
    }
    return "";
  };

  const subjectSelector = useMemo(() => {
    if (!user) return null;
    if (user.user_type === "customer") {
      const primaryId = user.subject_ids[0] ?? "";
      return primaryId ? (
        <span className="app-user-chip">Cuenta: {primaryId}</span>
      ) : null;
    }

    const options =
      subjects && subjects.length > 0
        ? subjects.map((s) => s.subject_id)
        : user.subject_ids;

    const canQueryPublicOnly = user.can_access_all_subjects;

    if (!canQueryPublicOnly && options.length === 0) {
      return null;
    }

    const subjectNameMap = new Map(
      subjects?.map((s) => [s.subject_id, s.display_name]) ?? []
    );

    const helperText = getSelectorHelperText();

    return (
      <div className="app-subject-selector">
        <label>
          Contexto activo:
          <select
            value={getCurrentSelectorValue()}
            onChange={(e) => handleContextChange(e.target.value)}
          >
            {canQueryPublicOnly && (
              <>
                <optgroup label="Documentacion">
                  <option value="public_docs">Documentacion Publica</option>
                  <option value="educational">Material Educativo</option>
                </optgroup>
                {options.length > 0 && (
                  <optgroup label="Alumnos">
                    {options.map((id) => {
                      const displayName = subjectNameMap.get(id);
                      const label =
                        displayName && displayName !== id
                          ? `${displayName} (${id})`
                          : id;
                      return (
                        <option key={id} value={id}>
                          {label}
                        </option>
                      );
                    })}
                  </optgroup>
                )}
              </>
            )}
            {!canQueryPublicOnly &&
              options.map((id) => {
                const displayName = subjectNameMap.get(id);
                const label =
                  displayName && displayName !== id
                    ? `${displayName} (${id})`
                    : id;
                return (
                  <option key={id} value={id}>
                    {label}
                  </option>
                );
              })}
          </select>
        </label>
        {helperText && <span className="selector-helper">{helperText}</span>}
      </div>
    );
  }, [user, selectedSubjectId, contextType, subjects]);

  // Loading state
  if (appState === "loading") {
    return (
      <div className="system-loading">
        <div className="spinner"></div>
        <p>Verificando estado del sistema...</p>
      </div>
    );
  }

  // Setup wizard for first run
  if (appState === "setup" && systemStatus) {
    return (
      <SetupWizard
        systemStatus={systemStatus}
        onSetupComplete={handleSetupComplete}
      />
    );
  }

  // Login screen
  if (appState === "login" || !token || !user) {
    return (
      <div className="app-root">
        <header className="app-header">
          <div>
            <h1>Cortex</h1>
            <p className="app-subtitle">
              Plataforma empresarial · Asistente de conocimiento seguro
            </p>
          </div>
        </header>
        <div className="app-body app-body-centered">
          <Login />
        </div>
      </div>
    );
  }

  // Check if user is admin for showing admin tabs
  const isAdmin = user.user_type === "employee" && user.role === "admin";

  // Render main content based on view
  const renderMainContent = () => {
    switch (mainView) {
      case "chat":
        return (
          <>
            <SidePanel
              subjectId={
                user.user_type === "employee"
                  ? selectedSubjectId
                  : user.subject_ids[0] ?? null
              }
              userType={user.user_type}
              onSubjectsChanged={refreshSubjects}
            />
            <Chat
              subjectId={
                user.user_type === "employee" ? selectedSubjectId : null
              }
              contextType={user.user_type === "employee" ? contextType : null}
              messages={chatMessages}
              setMessages={setChatMessages}
            />
          </>
        );
      case "users":
        return (
          <div className="full-page-content">
            <UserManagement onSubjectsChanged={refreshSubjects} />
          </div>
        );
      case "transactional":
        return (
          <div className="full-page-content">
            <TransactionalPanel />
          </div>
        );
      case "documents":
        return (
          <div className="full-page-content">
            <DocumentManagement />
          </div>
        );
      default:
        return null;
    }
  };

  // Authenticated main app
  return (
    <div className="app-root">
      <header className="app-header">
        <div>
          <h1>Cortex</h1>
          <p className="app-subtitle">
            {user.user_type === "customer"
              ? "Mi cuenta · Usuario autenticado"
              : `Portal Cortex · Rol: ${user.role}`}
          </p>
        </div>
        <div className="app-user-info">
          {/* Navigation tabs for admins */}
          {isAdmin && (
            <nav className="app-nav-tabs">
              <button
                className={`nav-tab ${mainView === "chat" ? "active" : ""}`}
                onClick={() => setMainView("chat")}
              >
                Chat
              </button>
              <button
                className={`nav-tab ${mainView === "users" ? "active" : ""}`}
                onClick={() => setMainView("users")}
              >
                Usuarios
              </button>
              <button
                className={`nav-tab ${
                  mainView === "transactional" ? "active" : ""
                }`}
                onClick={() => setMainView("transactional")}
              >
                {domainLabels.transactionalTabLabel}
              </button>
              <button
                className={`nav-tab ${
                  mainView === "documents" ? "active" : ""
                }`}
                onClick={() => setMainView("documents")}
              >
                Documentos
              </button>
            </nav>
          )}
          {mainView === "chat" && (
            <>
              {subjectSelector}
              {/* Context badge showing active context */}
              {(() => {
                const badge = getContextBadge();
                return badge ? (
                  <span
                    className={`context-badge ${badge.className}`}
                    data-tooltip={getSelectorHelperText()}
                    aria-label={`Contexto activo: ${badge.label}`}
                  >
                    <span aria-hidden="true">{badge.icon}</span>
                    <span>{badge.label}</span>
                  </span>
                ) : null;
              })()}
            </>
          )}
          <span className="app-user-chip">
            {user.username} ({user.user_type}/{user.role})
          </span>
          <button className="logout-button" onClick={handleSecureLogout}>
            Cerrar sesion
          </button>
          {showResetTimer && <DemoResetCountdown compact />}
        </div>
      </header>
      <div className="app-body">{renderMainContent()}</div>
    </div>
  );
};
