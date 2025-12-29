/**
 * DemoCredentialsPanel - Displays demo credentials for live demo environments.
 *
 * This component is ONLY rendered when VITE_DEMO_MODE is set to a valid demo type.
 * It provides visitors with ready-to-use credentials to test the application.
 *
 * Security Note: These are intentionally public demo credentials.
 * Never use this component in production environments.
 *
 * @module DemoCredentialsPanel
 */

import React, { useState } from "react";

/**
 * Credential entry for demo users
 */
export interface DemoCredential {
  role: string;
  username: string;
  password: string;
  description?: string;
}

/**
 * Configuration for the demo credentials panel
 */
export interface DemoCredentialsPanelConfig {
  title: string;
  subtitle: string;
  warningText: string;
  credentials: DemoCredential[];
}

interface DemoCredentialsPanelProps {
  config: DemoCredentialsPanelConfig;
  onCredentialClick?: (credential: DemoCredential) => void;
}

/**
 * Collapsible panel displaying demo credentials with copy functionality.
 *
 * Features:
 * - Collapsible to reduce visual noise
 * - Click-to-copy credentials
 * - Clear warning that this is a demo environment
 * - Accessible keyboard navigation
 */
export const DemoCredentialsPanel: React.FC<DemoCredentialsPanelProps> = ({
  config,
  onCredentialClick,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleCopy = async (text: string, fieldId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(fieldId);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleCredentialSelect = (credential: DemoCredential) => {
    if (onCredentialClick) {
      onCredentialClick(credential);
    }
  };

  return (
    <div
      className="demo-credentials-panel"
      role="region"
      aria-label="Demo Credentials"
    >
      {/* Warning Banner */}
      <div className="demo-warning-banner" role="alert">
        <span className="demo-warning-icon" aria-hidden="true">
          [!]
        </span>
        <span className="demo-warning-text">{config.warningText}</span>
      </div>

      {/* Collapsible Header */}
      <button
        className="demo-credentials-header"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-controls="demo-credentials-content"
      >
        <div className="demo-credentials-title-group">
          <h3 className="demo-credentials-title">{config.title}</h3>
          <p className="demo-credentials-subtitle">{config.subtitle}</p>
        </div>
        <span
          className={`demo-credentials-chevron ${isExpanded ? "expanded" : ""}`}
          aria-hidden="true"
        >
          ▼
        </span>
      </button>

      {/* Credentials Table */}
      {isExpanded && (
        <div id="demo-credentials-content" className="demo-credentials-content">
          <table className="demo-credentials-table" role="grid">
            <thead>
              <tr>
                <th scope="col">Rol</th>
                <th scope="col">Usuario</th>
                <th scope="col">Contraseña</th>
                <th scope="col" className="demo-action-col">
                  Acción
                </th>
              </tr>
            </thead>
            <tbody>
              {config.credentials.map((cred, index) => (
                <tr key={`${cred.role}-${index}`}>
                  <td className="demo-cred-role">
                    <span
                      className={`demo-role-badge demo-role-${cred.role.toLowerCase()}`}
                    >
                      {cred.role}
                    </span>
                  </td>
                  <td className="demo-cred-username">
                    <code
                      className={`demo-cred-value ${
                        copiedField === `user-${index}` ? "copied" : ""
                      }`}
                      onClick={() => handleCopy(cred.username, `user-${index}`)}
                      title="Click para copiar"
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) =>
                        e.key === "Enter" &&
                        handleCopy(cred.username, `user-${index}`)
                      }
                    >
                      {cred.username}
                      {copiedField === `user-${index}` && (
                        <span className="demo-copied-badge">✓</span>
                      )}
                    </code>
                  </td>
                  <td className="demo-cred-password">
                    <code
                      className={`demo-cred-value ${
                        copiedField === `pass-${index}` ? "copied" : ""
                      }`}
                      onClick={() => handleCopy(cred.password, `pass-${index}`)}
                      title="Click para copiar"
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) =>
                        e.key === "Enter" &&
                        handleCopy(cred.password, `pass-${index}`)
                      }
                    >
                      {cred.password}
                      {copiedField === `pass-${index}` && (
                        <span className="demo-copied-badge">✓</span>
                      )}
                    </code>
                  </td>
                  <td className="demo-action-col">
                    <button
                      className="demo-use-btn"
                      onClick={() => handleCredentialSelect(cred)}
                      title={`Usar credenciales de ${cred.role}`}
                    >
                      Usar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="demo-credentials-hint">
            Haz clic en cualquier valor para copiarlo, o usa el botón "Usar"
            para autocompletar.
          </p>
        </div>
      )}
    </div>
  );
};

export default DemoCredentialsPanel;
