import React, { useState, useEffect } from "react";
import { listUsers } from "../services/api";
import { useAuth } from "./AuthContext";
import { getDomainLabels } from "../config/domainLabels";

// Get labels at module load
const domainLabels = getDomainLabels();

interface AdminPanelProps {
  onSubjectsChanged?: () => void;
}

export const AdminPanel: React.FC<AdminPanelProps> = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<{
    totalUsers: number;
    employees: number;
    customers: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const isAdmin = user?.user_type === "employee" && user?.role === "admin";

  useEffect(() => {
    if (!isAdmin) return;
    loadStats();
  }, [isAdmin]);

  const loadStats = async () => {
    setLoading(true);
    try {
      const users = await listUsers();
      setStats({
        totalUsers: users.length,
        employees: users.filter((u) => u.user_type === "employee").length,
        customers: users.filter((u) => u.user_type === "customer").length,
      });
    } catch (e) {
      console.error("Error loading admin stats:", e);
    } finally {
      setLoading(false);
    }
  };

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="admin-panel-compact">
      <h3>Panel Admin</h3>

      {loading ? (
        <p className="loading-text">Cargando...</p>
      ) : stats ? (
        <div className="admin-quick-stats">
          <div className="stat-item">
            <span className="stat-number">{stats.totalUsers}</span>
            <span className="stat-label">Usuarios</span>
          </div>
          <div className="stat-item">
            <span className="stat-number">{stats.employees}</span>
            <span className="stat-label">{domainLabels.employees}</span>
          </div>
          <div className="stat-item">
            <span className="stat-number">{stats.customers}</span>
            <span className="stat-label">{domainLabels.subjects}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default AdminPanel;
