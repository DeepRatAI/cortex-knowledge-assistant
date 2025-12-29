import React, { useEffect, useState } from "react";
import {
  CustomerSnapshot,
  getCustomerSnapshot,
  getMySnapshot,
} from "../services/api";
import { useAuth } from "./AuthContext";

interface CustomerSnapshotPanelProps {
  subjectId: string | null;
}

export const CustomerSnapshotPanel: React.FC<CustomerSnapshotPanelProps> = ({
  subjectId,
}) => {
  const { user } = useAuth();
  const [snapshot, setSnapshot] = useState<CustomerSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!user) return;
      setLoading(true);
      setError(null);
      setSnapshot(null);
      try {
        let data: CustomerSnapshot;
        if (user.user_type === "customer") {
          data = await getMySnapshot();
        } else if (user.user_type === "employee" && subjectId) {
          data = await getCustomerSnapshot(subjectId);
        } else {
          return;
        }
        if (!cancelled) {
          setSnapshot(data);
        }
      } catch (e: any) {
        if (!cancelled) {
          // Mostrar mensaje amigable si no hay datos (404)
          const errorMsg = e?.message || "";
          if (
            errorMsg.includes("404") ||
            errorMsg.toLowerCase().includes("not found") ||
            errorMsg.includes("No transactional data")
          ) {
            setError(
              "Este cliente aun no tiene datos transaccionales registrados."
            );
          } else {
            setError("No se pudo cargar el resumen del cliente.");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [user, subjectId]);

  if (!user) return null;

  if (user.user_type === "employee" && !subjectId) {
    return (
      <section className="panel-section">
        <h2>Resumen del perfil</h2>
        <p className="panel-text">
          Selecciona un contexto para ver su resumen.
        </p>
      </section>
    );
  }

  return (
    <section className="panel-section">
      <h2>Resumen del perfil</h2>
      {loading && <p className="panel-text">Cargando resumen...</p>}
      {error && <p className="panel-text panel-error">{error}</p>}
      {!loading && !error && snapshot && (
        <div className="panel-text">
          <p>
            <strong>Cliente:</strong> {snapshot.subject_key}
          </p>
          {snapshot.products.length > 0 && (
            <div className="panel-attributes">
              <strong>Productos:</strong>
              <ul>
                {snapshot.products.map((p) => (
                  <li key={`${p.service_type}-${p.service_key}`}>
                    {p.service_type} {p.service_key}  {p.status}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {snapshot.recent_transactions.length > 0 && (
            <div className="panel-attributes">
              <strong>Movimientos recientes:</strong>
              <ul>
                {snapshot.recent_transactions.map((t, idx) => (
                  <li key={`${t.timestamp}-${idx}`}>
                    {new Date(t.timestamp).toLocaleDateString()} {" "}
                    {t.transaction_type}: {t.amount.toFixed(2)} {t.currency}{" "}
                    {t.description ? `  ${t.description}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {snapshot.products.length === 0 &&
            snapshot.recent_transactions.length === 0 && (
              <p>No hay datos transaccionales disponibles para este cliente.</p>
            )}
        </div>
      )}
    </section>
  );
};
