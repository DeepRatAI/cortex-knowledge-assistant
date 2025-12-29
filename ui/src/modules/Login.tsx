import React, { useState } from "react";
import { useAuth } from "./AuthContext";
import { DemoCredentialsPanel, DemoCredential } from "./DemoCredentialsPanel";
import { DemoResetCountdown } from "./DemoResetCountdown";
import {
  getDemoCredentialsConfig,
  shouldShowDemoCredentials,
  shouldShowDemoResetTimer,
} from "../config/domainLabels";

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    user_type: string;
    role: string;
    dlp_level: string;
    can_access_all_subjects: boolean;
    subject_ids: string[];
  };
}

// Use relative URLs - nginx proxy handles /auth/* routing
const API_BASE_URL = "";

export const Login: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Get demo credentials config if applicable
  const demoConfig = getDemoCredentialsConfig();
  const showDemoPanel = shouldShowDemoCredentials() && demoConfig !== null;
  const showResetTimer = shouldShowDemoResetTimer();

  /**
   * Handle credential selection from demo panel.
   * Auto-fills the login form with selected credentials.
   */
  const handleCredentialSelect = (credential: DemoCredential) => {
    setUsername(credential.username);
    setPassword(credential.password);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const u = username.trim();
    const p = password.trim();
    if (!u || !p) {
      setError("Usuario y contraseña son obligatorios");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const detail = body?.detail ?? "Credenciales inválidas";
        throw new Error(detail);
      }
      const data = (await res.json()) as LoginResponse;
      login({
        token: data.access_token,
        user: {
          id: data.user.id,
          username: data.user.username,
          user_type: data.user.user_type,
          role: data.user.role,
          dlp_level: data.user.dlp_level,
          can_access_all_subjects: data.user.can_access_all_subjects,
          subject_ids: data.user.subject_ids,
        },
      });
      setPassword("");
    } catch (err: any) {
      setError(err?.message || "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-content-wrapper">
        <h2>Iniciar sesión</h2>
        <p className="login-subtitle">
          Ingresa tus credenciales corporativas para acceder al sistema.
        </p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            Usuario
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error && <div className="login-error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? "Ingresando..." : "Ingresar"}
          </button>
        </form>

        {/* Demo Credentials Panel - Only shown in demo modes */}
        {showDemoPanel && demoConfig && (
          <DemoCredentialsPanel
            config={demoConfig}
            onCredentialClick={handleCredentialSelect}
          />
        )}

        {/* Demo Reset Countdown - For firstrun demo mode */}
        {showResetTimer && <DemoResetCountdown />}
      </div>
    </div>
  );
};
