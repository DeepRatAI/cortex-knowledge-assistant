/**
 * DocumentManagement.tsx
 *
 * Full-screen document management module for RAG system.
 * Handles document uploads, indexing, and monitoring.
 */

import React, { useState, useEffect, useRef } from "react";
import {
  adminUploadPublicDocument,
  refreshPublicDocs,
  listAuditLog,
  AuditLogEntry,
} from "../services/api";
import { useAuth } from "./AuthContext";
import {
  SuccessIcon,
  ErrorIcon,
  WarningIcon,
  DocumentIcon,
  DataIcon,
  ICON_SIZES,
} from "../components/Icons";

// =============================================================================
// FILE UPLOAD COMPONENT
// =============================================================================

interface FileUploadProps {
  onUploadComplete: () => void;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadComplete }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [category, setCategory] = useState<"public_docs" | "educational">(
    "public_docs"
  );
  const [progress, setProgress] = useState<{
    current: number;
    total: number;
    currentFile: string;
  } | null>(null);
  const [results, setResults] = useState<
    Array<{
      filename: string;
      success: boolean;
      message: string;
      hash?: string;
    }>
  >([]);
  const [error, setError] = useState<string | null>(null);

  const ALLOWED_EXTENSIONS = new Set([".pdf", ".txt", ".md"]);
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const validFiles: File[] = [];
    const errors: string[] = [];

    for (const file of files) {
      const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
      if (!ALLOWED_EXTENSIONS.has(ext)) {
        errors.push(`${file.name}: Tipo no permitido (solo PDF, TXT, MD)`);
      } else if (file.size > MAX_FILE_SIZE) {
        errors.push(`${file.name}: Excede el tamaño máximo (50MB)`);
      } else {
        validFiles.push(file);
      }
    }

    if (errors.length > 0) {
      setError(errors.join("\n"));
    } else {
      setError(null);
    }

    setSelectedFiles(validFiles);
    setResults([]);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;

    setUploading(true);
    setError(null);
    setResults([]);

    const uploadResults: typeof results = [];

    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i];
      setProgress({
        current: i + 1,
        total: selectedFiles.length,
        currentFile: file.name,
      });

      try {
        const response = await adminUploadPublicDocument(file, category);
        uploadResults.push({
          filename: file.name,
          success: true,
          message: response.message,
          hash: response.file_hash,
        });
      } catch (e: unknown) {
        const err = e as Error;
        uploadResults.push({
          filename: file.name,
          success: false,
          message: err?.message || "Error desconocido",
        });
      }
    }

    setResults(uploadResults);
    setProgress(null);
    setUploading(false);
    setSelectedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onUploadComplete();
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const files = Array.from(e.dataTransfer.files);
    const validFiles = files.filter((file) => {
      const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
      return ALLOWED_EXTENSIONS.has(ext) && file.size <= MAX_FILE_SIZE;
    });
    setSelectedFiles(validFiles);
    setResults([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      fileInputRef.current?.click();
    }
  };

  return (
    <div className="file-upload-section">
      <div
        className={`drop-zone ${selectedFiles.length > 0 ? "has-files" : ""}`}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-label="Área de carga de archivos"
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />
        <div className="drop-zone-content">
          <span className="drop-icon">[DOC]</span>
          <p className="drop-text">
            {selectedFiles.length > 0
              ? `${selectedFiles.length} archivo(s) seleccionado(s)`
              : "Arrastra archivos aquí o haz clic para seleccionar"}
          </p>
          <p className="drop-hint">PDF, TXT, MD - Máximo 50MB por archivo</p>
        </div>
      </div>

      {/* Category selector */}
      <div className="category-selector">
        <label htmlFor="doc-category">Categoría del documento:</label>
        <select
          id="doc-category"
          value={category}
          onChange={(e) =>
            setCategory(e.target.value as "public_docs" | "educational")
          }
          disabled={uploading}
        >
          <option value="public_docs">Documentación Institucional</option>
          <option value="educational">
            Material Educativo (Libros/Textos)
          </option>
        </select>
      </div>

      {/* Selected files list */}
      {selectedFiles.length > 0 && (
        <div className="selected-files">
          <h4>Archivos seleccionados:</h4>
          <ul>
            {selectedFiles.map((file) => (
              <li key={file.name}>
                <span className="file-name">{file.name}</span>
                <span className="file-size">
                  ({(file.size / 1024).toFixed(1)} KB)
                </span>
              </li>
            ))}
          </ul>
          <div className="upload-actions">
            <button
              className="btn-primary"
              onClick={handleUpload}
              disabled={uploading}
            >
              {uploading ? "Subiendo..." : "Subir e Indexar"}
            </button>
            <button
              className="btn-secondary"
              onClick={() => {
                setSelectedFiles([]);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
              disabled={uploading}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Progress indicator */}
      {progress && (
        <div className="upload-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(progress.current / progress.total) * 100}%` }}
            />
          </div>
          <p>
            Subiendo {progress.current} de {progress.total}:{" "}
            {progress.currentFile}
          </p>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="upload-error">
          <pre>{error}</pre>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="upload-results">
          <h4>Resultados:</h4>
          <ul>
            {results.map((result) => (
              <li
                key={result.filename}
                className={result.success ? "success" : "error"}
              >
                <span className="result-icon">
                  {result.success ? "[OK]" : "[X]"}
                </span>
                <span className="result-filename">{result.filename}</span>
                <span className="result-message">{result.message}</span>
                {result.hash && (
                  <span className="result-hash" title={result.hash}>
                    SHA: {result.hash.substring(0, 8)}...
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// =============================================================================
// DOCUMENT AUDIT LOG
// =============================================================================

interface DocumentAuditLogProps {
  refreshTrigger: number;
}

const DocumentAuditLog: React.FC<DocumentAuditLogProps> = ({
  refreshTrigger,
}) => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadLogs();
  }, [refreshTrigger]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const allLogs = await listAuditLog();
      const docLogs = allLogs.filter(
        (log) =>
          log.operation?.includes("document") ||
          log.operation?.includes("upload") ||
          log.operation?.includes("ingest")
      );
      setLogs(docLogs);
      setError(null);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al cargar logs");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading-state">Cargando historial...</div>;
  }

  if (error) {
    return <div className="error-state">{error}</div>;
  }

  if (logs.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-state-icon" aria-hidden="true">
          <DataIcon size={48} />
        </span>
        <p className="empty-state-title">Sin registros de documentos</p>
        <p className="empty-state-description">
          Las operaciones de carga, indexacion y eliminacion de documentos
          apareceran aqui.
        </p>
      </div>
    );
  }

  return (
    <div className="audit-log-section">
      <table className="audit-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Operacion</th>
            <th>Usuario</th>
            <th>Resultado</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{new Date(log.created_at).toLocaleString()}</td>
              <td>
                <span className={`action-badge ${log.outcome}`}>
                  {log.operation}
                </span>
              </td>
              <td>{log.username || `ID: ${log.user_id}`}</td>
              <td>{log.outcome}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// =============================================================================
// QDRANT STATUS COMPONENT
// =============================================================================

const QdrantStatus: React.FC = () => {
  const [status, setStatus] = useState<{
    reachable: boolean;
    collection_exists: boolean;
    document_count: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    setLoading(true);
    try {
      // Use relative URL - nginx proxy handles /api/* routing
      const res = await fetch("/api/system/status");
      if (res.ok) {
        const data = await res.json();
        setStatus(data.qdrant);
        setError(null);
      } else {
        setError("No se pudo obtener el estado");
      }
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error de conexión");
    } finally {
      setLoading(false);
    }
  };

  const handleReindex = async () => {
    setReindexing(true);
    setMessage(null);
    setError(null);
    try {
      const result = await refreshPublicDocs();
      setMessage(`Indexación completada: ${result.status}`);
      checkStatus();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || "Error al reindexar");
    } finally {
      setReindexing(false);
    }
  };

  return (
    <div className="qdrant-status-section">
      <h3>Estado del Sistema RAG</h3>

      {loading ? (
        <div className="loading-state">Verificando estado...</div>
      ) : (
        <div className="status-cards">
          <div
            className={`status-card ${status?.reachable ? "ok" : "error"}`}
            data-tooltip={
              status?.reachable
                ? "Base de datos vectorial operativa y respondiendo"
                : "No se puede conectar a Qdrant. Verifique que el servicio este activo"
            }
          >
            <span className="status-icon" aria-hidden="true">
              {status?.reachable ? (
                <SuccessIcon size={ICON_SIZES.lg} />
              ) : (
                <ErrorIcon size={ICON_SIZES.lg} />
              )}
            </span>
            <span className="status-label">Qdrant</span>
            <span className="status-value">
              {status?.reachable ? "Conectado" : "Desconectado"}
            </span>
          </div>

          <div
            className={`status-card ${
              status?.collection_exists ? "ok" : "warning"
            }`}
            data-tooltip={
              status?.collection_exists
                ? "La coleccion de documentos existe y esta lista para consultas"
                : "No hay coleccion creada. Suba documentos para crearla automaticamente"
            }
          >
            <span className="status-icon" aria-hidden="true">
              {status?.collection_exists ? (
                <SuccessIcon size={ICON_SIZES.lg} />
              ) : (
                <WarningIcon size={ICON_SIZES.lg} />
              )}
            </span>
            <span className="status-label">Coleccion</span>
            <span className="status-value">
              {status?.collection_exists ? "Existe" : "No existe"}
            </span>
          </div>

          <div
            className="status-card info"
            data-tooltip="Numero total de documentos indexados disponibles para busqueda RAG"
          >
            <span className="status-icon" aria-hidden="true">
              <DocumentIcon size={ICON_SIZES.lg} />
            </span>
            <span className="status-label">Documentos</span>
            <span className="status-value">{status?.document_count ?? 0}</span>
          </div>
        </div>
      )}

      {/* Instrucciones de carga manual */}
      <div className="manual-upload-info">
        <h4>Carga Manual de Documentos</h4>
        <p>
          Para cargar documentos directamente en el servidor sin usar la
          interfaz web, copie los archivos (PDF, TXT, MD) a la siguiente ruta:
        </p>
        <code className="path-display">./documentacion/publica/</code>
        <p className="info-note">
          Ruta relativa al directorio raiz del proyecto. Luego presione
          "Re-indexar Documentos" para procesar los nuevos archivos.
        </p>
      </div>

      <div className="status-actions">
        <button
          className="btn-secondary"
          onClick={checkStatus}
          disabled={loading}
        >
          Actualizar Estado
        </button>
        <button
          className="btn-primary"
          onClick={handleReindex}
          disabled={reindexing || !status?.reachable}
        >
          {reindexing ? "Indexando..." : "Re-indexar Documentos"}
        </button>
      </div>

      {error && <div className="status-error">{error}</div>}
      {message && <div className="status-message">{message}</div>}
    </div>
  );
};

// =============================================================================
// MAIN DOCUMENT MANAGEMENT COMPONENT
// =============================================================================

export const DocumentManagement: React.FC = () => {
  const { user } = useAuth();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [activeTab, setActiveTab] = useState<"upload" | "status" | "history">(
    "upload"
  );

  const isAdmin = user?.user_type === "employee" && user?.role === "admin";

  const handleUploadComplete = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  if (!isAdmin) {
    return (
      <div className="access-denied">
        <h2>Acceso Denegado</h2>
        <p>
          Solo los administradores pueden acceder a la gestión de documentos.
        </p>
      </div>
    );
  }

  return (
    <div className="document-management-page">
      <header className="page-header">
        <h2>Gestión de Documentos</h2>
        <p className="page-description">
          Administración del sistema RAG: carga, indexación y monitoreo de
          documentos.
        </p>
      </header>

      {/* Tab navigation */}
      <div className="page-tabs">
        <button
          className={`page-tab ${activeTab === "upload" ? "active" : ""}`}
          onClick={() => setActiveTab("upload")}
        >
          Cargar Documentos
        </button>
        <button
          className={`page-tab ${activeTab === "status" ? "active" : ""}`}
          onClick={() => setActiveTab("status")}
        >
          Estado RAG
        </button>
        <button
          className={`page-tab ${activeTab === "history" ? "active" : ""}`}
          onClick={() => setActiveTab("history")}
        >
          Historial
        </button>
      </div>

      {/* Tab content */}
      <div className="page-content">
        {activeTab === "upload" && (
          <div className="tab-panel">
            <div className="panel-info">
              <h3>Cargar Documentación Pública</h3>
              <p>
                Los documentos cargados aquí estarán disponibles para consultas
                RAG de todos los usuarios. Los archivos se indexan
                automáticamente en Qdrant y quedan registrados con hash SHA-256
                para auditoría.
              </p>
            </div>
            <FileUpload onUploadComplete={handleUploadComplete} />
          </div>
        )}

        {activeTab === "status" && (
          <div className="tab-panel">
            <QdrantStatus />
          </div>
        )}

        {activeTab === "history" && (
          <div className="tab-panel">
            <div className="panel-info">
              <h3>Historial de Operaciones</h3>
              <p>Registro completo de cargas e indexaciones de documentos.</p>
            </div>
            <DocumentAuditLog refreshTrigger={refreshTrigger} />
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentManagement;
