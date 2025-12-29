import React, { useEffect, useState } from "react";
import {
  getSubjectDetail,
  listSubjectServices,
  SubjectDetail,
  SubjectServiceSummary,
} from "../services/api";

interface SubjectContextPanelProps {
  subjectId: string | null;
  userType: string;
}

export const SubjectContextPanel: React.FC<SubjectContextPanelProps> = ({
  subjectId,
  userType,
}) => {
  const [detail, setDetail] = useState<SubjectDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [services, setServices] = useState<SubjectServiceSummary[]>([]);
  const [servicesError, setServicesError] = useState<string | null>(null);

  useEffect(() => {
    if (!subjectId) {
      setDetail(null);
      setError(null);
      setServices([]);
      setServicesError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setServicesError(null);
    void (async () => {
      try {
        const [detailData, servicesData] = await Promise.all([
          getSubjectDetail(subjectId),
          listSubjectServices(subjectId),
        ]);
        if (!cancelled) {
          setDetail(detailData);
          setServices(servicesData);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(
            e?.message || "No se pudo cargar el contexto del cliente actual."
          );
          setDetail(null);
          setServices([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [subjectId]);

  if (userType !== "employee") {
    return null;
  }

  return (
    <section className="panel-section">
      <h2>Cliente activo</h2>
      {!subjectId && (
        <p className="panel-text">
          Selecciona un cliente para ver su contexto.
        </p>
      )}
      {subjectId && loading && (
        <p className="panel-text">Cargando contexto del cliente...</p>
      )}
      {subjectId && error && <p className="panel-text panel-error">{error}</p>}
      {subjectId && !loading && !error && detail && (
        <div className="panel-text">
          <p>
            <strong>ID:</strong> {detail.subject_id}
          </p>
          <p>
            <strong>Nombre:</strong> {detail.display_name}
          </p>
          <p>
            <strong>Tipo:</strong> {detail.subject_type}
          </p>
          <p>
            <strong>Estado:</strong> {detail.status}
          </p>
          {detail.attributes && Object.keys(detail.attributes).length > 0 && (
            <div className="panel-attributes">
              <strong>Atributos:</strong>
              <ul>
                {Object.entries(detail.attributes).map(([key, value]) => (
                  <li key={key}>
                    <strong>{key}:</strong> {String(value)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {servicesError && (
            <p className="panel-text panel-error">{servicesError}</p>
          )}
          {services.length > 0 && (
            <div className="panel-attributes">
              <strong>Servicios:</strong>
              <ul>
                {services.map((svc) => (
                  <li
                    key={`${svc.service_type}-${svc.service_key}`}
                    className="panel-service-item"
                  >
                    <span>
                      {svc.display_name} ({svc.service_type}) — {svc.status}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
