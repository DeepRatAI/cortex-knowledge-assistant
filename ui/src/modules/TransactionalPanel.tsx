import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  adminListSubjects,
  adminListProducts,
  adminCreateProduct,
  adminUpdateProduct,
  adminDeleteProduct,
  adminListTransactions,
  adminCreateTransaction,
  adminUpdateTransaction,
  adminDeleteTransaction,
  AdminSubjectSummary,
  ServiceInstanceResponse,
  ServiceInstanceCreate,
  TransactionResponse,
  TransactionCreate,
  TransactionListResponse,
} from "../services/api";
import { useAuth } from "./AuthContext";
import { getDomainLabels } from "../config/domainLabels";

// =============================================================================
// DOMAIN LABELS - Dynamic configuration based on VITE_DEMO_DOMAIN
// =============================================================================

// Get labels at module load (changes require app restart)
const domainLabels = getDomainLabels();

// Service/Product types from domain configuration
const SERVICE_TYPE_GROUPS = domainLabels.serviceTypeGroups;

// Flat list for backward compatibility and simple lookups
const SERVICE_TYPES = SERVICE_TYPE_GROUPS.flatMap((g) => g.types);

// Transaction types from domain configuration
const TRANSACTION_TYPE_GROUPS = domainLabels.transactionTypeGroups;

// Flat list for backward compatibility
const TRANSACTION_TYPES = TRANSACTION_TYPE_GROUPS.flatMap((g) => g.types);

const STATUS_OPTIONS = [
  { value: "active", label: "Activo" },
  { value: "closed", label: "Cerrado" },
  { value: "suspended", label: "Suspendido" },
  { value: "pending", label: "Pendiente" },
  { value: "cancelled", label: "Cancelado" },
];

// =============================================================================
// AMOUNT FORMATTING HELPER
// =============================================================================
// Handles both ISO currency codes (EUR, USD, ARS) and non-standard units (points)

const formatAmount = (amount: number, currency: string): string => {
  // List of valid ISO 4217 currency codes we support
  const validCurrencies = new Set([
    "EUR",
    "USD",
    "ARS",
    "MXN",
    "CLP",
    "COP",
    "PEN",
    "UYU",
    "BRL",
    "GBP",
  ]);

  if (validCurrencies.has(currency?.toUpperCase())) {
    return new Intl.NumberFormat("es-ES", {
      style: "currency",
      currency: currency.toUpperCase(),
    }).format(amount);
  }

  // For non-currency units like "points", format as decimal with unit suffix
  const formattedNumber = new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(amount);

  // Translate common unit names
  const unitLabels: Record<string, string> = {
    points: "pts",
    puntos: "pts",
    credits: "cr",
    creditos: "cr",
  };

  const unitLabel = unitLabels[currency?.toLowerCase()] || currency || "";
  return `${formattedNumber} ${unitLabel}`.trim();
};

// =============================================================================
// CREATE PRODUCT FORM
// =============================================================================

interface CreateProductFormProps {
  subjectKey: string;
  onProductCreated: () => void;
  onCancel: () => void;
}

const CreateProductForm: React.FC<CreateProductFormProps> = ({
  subjectKey,
  onProductCreated,
  onCancel,
}) => {
  const [formData, setFormData] = useState<ServiceInstanceCreate>({
    service_type: "bank_account",
    service_key: "",
    status: "active",
    extra_metadata: {},
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.service_key.trim()) {
      setError("El identificador del producto es requerido");
      return;
    }

    setLoading(true);
    try {
      await adminCreateProduct(subjectKey, formData);
      onProductCreated();
    } catch (e: unknown) {
      setError((e as Error)?.message || "Error al crear producto");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="create-product-form">
      <h4>Nuevo Producto para {subjectKey}</h4>
      {error && <p className="panel-error">{error}</p>}
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>
            Tipo de producto:
            <select
              value={formData.service_type}
              onChange={(e) =>
                setFormData({ ...formData, service_type: e.target.value })
              }
              disabled={loading}
            >
              {SERVICE_TYPE_GROUPS.map((group) => (
                <optgroup key={group.group} label={group.group}>
                  {group.types.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        </div>
        <div className="form-row">
          <label>
            Identificador (cuenta, contrato, poliza, etc.):
            <input
              type="text"
              value={formData.service_key}
              onChange={(e) =>
                setFormData({ ...formData, service_key: e.target.value })
              }
              placeholder="Ej: ES76-0000-0000-0000"
              disabled={loading}
            />
          </label>
        </div>
        <div className="form-row">
          <label>
            Estado:
            <select
              value={formData.status}
              onChange={(e) =>
                setFormData({ ...formData, status: e.target.value })
              }
              disabled={loading}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-actions">
          <button type="submit" className="admin-button" disabled={loading}>
            {loading ? "Creando..." : "Crear Producto"}
          </button>
          <button
            type="button"
            className="admin-button secondary"
            onClick={onCancel}
            disabled={loading}
          >
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
};

// =============================================================================
// CREATE TRANSACTION FORM
// =============================================================================

interface CreateTransactionFormProps {
  productId: number;
  productInfo: ServiceInstanceResponse;
  onTransactionCreated: () => void;
  onCancel: () => void;
}

const CreateTransactionForm: React.FC<CreateTransactionFormProps> = ({
  productId,
  productInfo,
  onTransactionCreated,
  onCancel,
}) => {
  const [formData, setFormData] = useState<TransactionCreate>({
    transaction_type: "credit",
    amount: 0,
    currency: "EUR",
    description: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.amount === 0) {
      setError("El monto no puede ser cero");
      return;
    }

    // Auto-adjust sign based on transaction type (negative for charges/debits)
    const DEBIT_TYPES = [
      "debit",
      "transfer_out",
      "fee",
      "service_charge",
      "maintenance_fee",
      "penalty",
      "late_fee",
      "overdraft_fee",
      "tax",
      "payment",
      "installment",
      "premium",
      "invoice",
      "bill",
      "subscription_charge",
      "renewal",
      "withdrawal",
      "interest_charged",
    ];
    let finalAmount = Math.abs(formData.amount);
    if (DEBIT_TYPES.includes(formData.transaction_type)) {
      finalAmount = -finalAmount;
    }

    setLoading(true);
    try {
      await adminCreateTransaction(productId, {
        ...formData,
        amount: finalAmount,
      });
      onTransactionCreated();
    } catch (e: unknown) {
      setError((e as Error)?.message || "Error al crear movimiento");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="create-transaction-form">
      <h4>
        Nuevo Movimiento - {productInfo.service_type} ({productInfo.service_key}
        )
      </h4>
      {error && <p className="panel-error">{error}</p>}
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>
            Tipo de movimiento:
            <select
              value={formData.transaction_type}
              onChange={(e) =>
                setFormData({ ...formData, transaction_type: e.target.value })
              }
              disabled={loading}
            >
              {TRANSACTION_TYPE_GROUPS.map((group) => (
                <optgroup key={group.group} label={group.group}>
                  {group.types.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        </div>
        <div className="form-row">
          <label>
            Monto (valor absoluto):
            <input
              type="number"
              step="0.01"
              min="0"
              value={Math.abs(formData.amount)}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  amount: parseFloat(e.target.value) || 0,
                })
              }
              disabled={loading}
            />
          </label>
          <span className="help-text">
            {[
              "debit",
              "transfer_out",
              "fee",
              "service_charge",
              "maintenance_fee",
              "penalty",
              "late_fee",
              "overdraft_fee",
              "tax",
              "payment",
              "installment",
              "premium",
              "invoice",
              "bill",
              "subscription_charge",
              "renewal",
            ].includes(formData.transaction_type)
              ? "Se registrara como negativo (cargo)"
              : "Se registrara como positivo (abono)"}
          </span>
        </div>
        <div className="form-row">
          <label>
            Moneda:
            <select
              value={formData.currency}
              onChange={(e) =>
                setFormData({ ...formData, currency: e.target.value })
              }
              disabled={loading}
            >
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
              <option value="ARS">ARS</option>
              <option value="GBP">GBP</option>
              <option value="MXN">MXN</option>
              <option value="CLP">CLP</option>
              <option value="COP">COP</option>
              <option value="PEN">PEN</option>
            </select>
          </label>
        </div>
        <div className="form-row">
          <label>
            Descripción:
            <input
              type="text"
              value={formData.description || ""}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              placeholder="Ingreso nómina, Pago comercio, etc."
              disabled={loading}
            />
          </label>
        </div>
        <div className="form-actions">
          <button type="submit" className="admin-button" disabled={loading}>
            {loading ? "Creando..." : "Crear Movimiento"}
          </button>
          <button
            type="button"
            className="admin-button secondary"
            onClick={onCancel}
            disabled={loading}
          >
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
};

// =============================================================================
// PRODUCT ROW COMPONENT
// =============================================================================

interface ProductRowProps {
  product: ServiceInstanceResponse;
  onRefresh: () => void;
  onViewTransactions: (product: ServiceInstanceResponse) => void;
}

const ProductRow: React.FC<ProductRowProps> = ({
  product,
  onRefresh,
  onViewTransactions,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({
    service_type: product.service_type,
    status: product.status,
  });
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    setLoading(true);
    try {
      await adminUpdateProduct(product.id, editData);
      setIsEditing(false);
      onRefresh();
    } catch (e) {
      console.error("Error updating product:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!globalThis.confirm(`¿Cerrar producto "${product.service_key}"?`)) {
      return;
    }
    setLoading(true);
    try {
      await adminDeleteProduct(product.id, false);
      onRefresh();
    } catch (e) {
      console.error("Error deleting product:", e);
    } finally {
      setLoading(false);
    }
  };

  const typeLabel =
    SERVICE_TYPES.find((t) => t.value === product.service_type)?.label ||
    product.service_type;

  return (
    <tr
      className={`product-row ${product.status !== "active" ? "inactive" : ""}`}
    >
      <td>{product.id}</td>
      <td>
        {isEditing ? (
          <select
            value={editData.service_type}
            onChange={(e) =>
              setEditData({ ...editData, service_type: e.target.value })
            }
            disabled={loading}
          >
            {SERVICE_TYPE_GROUPS.map((group) => (
              <optgroup key={group.group} label={group.group}>
                {group.types.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        ) : (
          typeLabel
        )}
      </td>
      <td className="service-key">{product.service_key}</td>
      <td>
        {isEditing ? (
          <select
            value={editData.status}
            onChange={(e) =>
              setEditData({ ...editData, status: e.target.value })
            }
            disabled={loading}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        ) : (
          <span className={`badge status-${product.status}`}>
            {product.status}
          </span>
        )}
      </td>
      <td className="date">
        {new Date(product.opened_at).toLocaleDateString()}
      </td>
      <td className="actions">
        {isEditing ? (
          <>
            <button
              className="btn-small btn-save"
              onClick={handleSave}
              disabled={loading}
            >
              {loading ? "..." : "Guardar"}
            </button>
            <button
              className="btn-small btn-cancel"
              onClick={() => setIsEditing(false)}
              disabled={loading}
            >
              Cancelar
            </button>
          </>
        ) : (
          <>
            <button
              className="btn-small btn-view"
              onClick={() => onViewTransactions(product)}
              title={`Ver ${domainLabels.transactions.toLowerCase()}`}
            >
              {domainLabels.transactions}
            </button>
            <button
              className="btn-small btn-edit"
              onClick={() => setIsEditing(true)}
            >
              Editar
            </button>
            {product.status === "active" && (
              <button
                className="btn-small btn-delete"
                onClick={handleDelete}
                disabled={loading}
              >
                Cerrar
              </button>
            )}
          </>
        )}
      </td>
    </tr>
  );
};

// =============================================================================
// TRANSACTION ROW COMPONENT
// =============================================================================

interface TransactionRowProps {
  tx: TransactionResponse;
  onRefresh: () => void;
}

const TransactionRow: React.FC<TransactionRowProps> = ({ tx, onRefresh }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({
    description: tx.description || "",
    amount: tx.amount,
  });
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    setLoading(true);
    try {
      await adminUpdateTransaction(tx.id, editData);
      setIsEditing(false);
      onRefresh();
    } catch (e) {
      console.error("Error updating transaction:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (
      !globalThis.confirm(
        `¿Eliminar este movimiento? Esta acción no se puede deshacer.`
      )
    ) {
      return;
    }
    setLoading(true);
    try {
      await adminDeleteTransaction(tx.id);
      onRefresh();
    } catch (e) {
      console.error("Error deleting transaction:", e);
    } finally {
      setLoading(false);
    }
  };

  const typeLabel =
    TRANSACTION_TYPES.find((t) => t.value === tx.transaction_type)?.label ||
    tx.transaction_type;

  const amountClass = tx.amount >= 0 ? "amount-positive" : "amount-negative";
  const amountFormatted = formatAmount(tx.amount, tx.currency);

  return (
    <tr className="transaction-row">
      <td className="date">
        {new Date(tx.timestamp).toLocaleDateString("es-ES", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        })}
      </td>
      <td>{typeLabel}</td>
      <td>
        {isEditing ? (
          <input
            type="text"
            value={editData.description}
            onChange={(e) =>
              setEditData({ ...editData, description: e.target.value })
            }
            disabled={loading}
          />
        ) : (
          tx.description || "-"
        )}
      </td>
      <td className={amountClass}>
        {isEditing ? (
          <input
            type="number"
            step="0.01"
            value={editData.amount}
            onChange={(e) =>
              setEditData({ ...editData, amount: parseFloat(e.target.value) })
            }
            disabled={loading}
          />
        ) : (
          amountFormatted
        )}
      </td>
      <td className="actions">
        {isEditing ? (
          <>
            <button
              className="btn-small btn-save"
              onClick={handleSave}
              disabled={loading}
            >
              {loading ? "..." : "✓"}
            </button>
            <button
              className="btn-small btn-cancel"
              onClick={() => setIsEditing(false)}
              disabled={loading}
            >
              ✕
            </button>
          </>
        ) : (
          <>
            <button
              className="btn-small btn-edit"
              onClick={() => setIsEditing(true)}
              title="Editar"
            >
              Editar
            </button>
            <button
              className="btn-small btn-delete"
              onClick={handleDelete}
              disabled={loading}
              title="Eliminar"
            >
              Eliminar
            </button>
          </>
        )}
      </td>
    </tr>
  );
};

// =============================================================================
// TRANSACTIONS VIEW
// =============================================================================

interface TransactionsViewProps {
  product: ServiceInstanceResponse;
  onBack: () => void;
}

const TransactionsView: React.FC<TransactionsViewProps> = ({
  product,
  onBack,
}) => {
  const [transactions, setTransactions] = useState<TransactionResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [filterType, setFilterType] = useState<string>("all");
  const [total, setTotal] = useState(0);

  const loadTransactions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result: TransactionListResponse = await adminListTransactions(
        product.id,
        {
          limit: 100,
          txType: filterType !== "all" ? filterType : undefined,
        }
      );
      setTransactions(result.transactions);
      setTotal(result.total);
    } catch (e: unknown) {
      setError(
        (e as Error)?.message ||
          `Error al cargar ${domainLabels.transactions.toLowerCase()}`
      );
    } finally {
      setLoading(false);
    }
  }, [product.id, filterType]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const balance = transactions.reduce((sum, tx) => sum + tx.amount, 0);
  const productCurrency = (product.extra_metadata?.currency as string) || "EUR";
  const balanceFormatted = formatAmount(balance, productCurrency);

  return (
    <div className="transactions-view">
      <div className="transactions-header">
        <button className="admin-button secondary" onClick={onBack}>
          ← Volver a {domainLabels.products.toLowerCase()}
        </button>
        <h4>
          {domainLabels.transactions} de {product.service_type} -{" "}
          {product.service_key}
        </h4>
        <div className="balance-display">
          Saldo calculado:{" "}
          <span
            className={balance >= 0 ? "amount-positive" : "amount-negative"}
          >
            {balanceFormatted}
          </span>
        </div>
      </div>

      <div className="transactions-toolbar">
        <button
          className="admin-button"
          onClick={() => setShowCreateForm(!showCreateForm)}
        >
          {showCreateForm ? "Cancelar" : "+ Nuevo movimiento"}
        </button>

        <label>
          Filtrar:
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="all">Todos</option>
            {TRANSACTION_TYPE_GROUPS.map((group) => (
              <optgroup key={group.group} label={group.group}>
                {group.types.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <span className="transaction-count">
          {transactions.length} de {total}{" "}
          {domainLabels.transactions.toLowerCase()}
        </span>
      </div>

      {showCreateForm && (
        <CreateTransactionForm
          productId={product.id}
          productInfo={product}
          onTransactionCreated={() => {
            setShowCreateForm(false);
            loadTransactions();
          }}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      {error && <p className="panel-error">{error}</p>}

      {loading ? (
        <p>Cargando {domainLabels.transactions.toLowerCase()}...</p>
      ) : transactions.length === 0 ? (
        <p className="empty-state">
          No hay {domainLabels.transactions.toLowerCase()} registrados para este{" "}
          {domainLabels.product.toLowerCase()}.
        </p>
      ) : (
        <div className="transactions-table-container">
          <table className="transactions-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Descripción</th>
                <th>Monto</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx) => (
                <TransactionRow
                  key={tx.id}
                  tx={tx}
                  onRefresh={loadTransactions}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// =============================================================================
// MAIN TRANSACTIONAL PANEL
// =============================================================================

export const TransactionalPanel: React.FC = () => {
  const { user } = useAuth();
  const [subjects, setSubjects] = useState<AdminSubjectSummary[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [products, setProducts] = useState<ServiceInstanceResponse[]>([]);
  const [viewingProduct, setViewingProduct] =
    useState<ServiceInstanceResponse | null>(null);

  const [subjectsLoading, setSubjectsLoading] = useState(false);
  const [productsLoading, setProductsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showCreateProduct, setShowCreateProduct] = useState(false);
  const [subjectFilter, setSubjectFilter] = useState<string>("active");
  const [productFilter, setProductFilter] = useState<string>("all");

  // Only render for admins
  if (!(user?.user_type === "employee" && user.role === "admin")) {
    return null;
  }

  const loadSubjects = async () => {
    setSubjectsLoading(true);
    setError(null);
    try {
      const result = await adminListSubjects(
        subjectFilter !== "all" ? subjectFilter : undefined
      );
      setSubjects(result.subjects);
    } catch (e: unknown) {
      setError(
        (e as Error)?.message ||
          `Error al cargar ${domainLabels.subjects.toLowerCase()}`
      );
    } finally {
      setSubjectsLoading(false);
    }
  };

  const loadProducts = async (subjectKey: string) => {
    setProductsLoading(true);
    setError(null);
    try {
      const result = await adminListProducts(
        subjectKey,
        productFilter !== "all" ? productFilter : undefined
      );
      setProducts(result.products);
    } catch (e: unknown) {
      setError(
        (e as Error)?.message ||
          `Error al cargar ${domainLabels.products.toLowerCase()}`
      );
    } finally {
      setProductsLoading(false);
    }
  };

  const handleSelectSubject = (subjectKey: string) => {
    setSelectedSubject(subjectKey);
    setViewingProduct(null);
    setShowCreateProduct(false);
    loadProducts(subjectKey);
  };

  const handleBackToSubjects = () => {
    setSelectedSubject(null);
    setProducts([]);
    setViewingProduct(null);
  };

  // Load subjects on mount and filter change
  useEffect(() => {
    loadSubjects();
  }, [subjectFilter]);

  // Reload products when filter changes
  useEffect(() => {
    if (selectedSubject) {
      loadProducts(selectedSubject);
    }
  }, [productFilter]);

  // If viewing transactions, show that view
  if (viewingProduct) {
    return (
      <section className="panel-section transactional-panel">
        <h2>{domainLabels.transactionalPanelTitle}</h2>
        <TransactionsView
          product={viewingProduct}
          onBack={() => setViewingProduct(null)}
        />
      </section>
    );
  }

  // If a subject is selected, show products
  if (selectedSubject) {
    const subjectInfo = subjects.find((s) => s.subject_key === selectedSubject);
    return (
      <section className="panel-section transactional-panel">
        <h2>{domainLabels.transactionalPanelTitle}</h2>

        <div className="products-header">
          <button
            className="admin-button secondary"
            onClick={handleBackToSubjects}
          >
            {domainLabels.backToSubjects}
          </button>
          <h3>
            {domainLabels.products} de{" "}
            {subjectInfo?.display_name || selectedSubject}
          </h3>
        </div>

        <div className="products-toolbar">
          <button
            className="admin-button"
            onClick={() => setShowCreateProduct(!showCreateProduct)}
          >
            {showCreateProduct
              ? "Cancelar"
              : `+ Nuevo ${domainLabels.product.toLowerCase()}`}
          </button>

          <label>
            Estado:
            <select
              value={productFilter}
              onChange={(e) => setProductFilter(e.target.value)}
            >
              <option value="all">Todos</option>
              <option value="active">Activos</option>
              <option value="closed">Cerrados</option>
            </select>
          </label>

          <button
            className="admin-button secondary"
            onClick={() => loadProducts(selectedSubject)}
            disabled={productsLoading}
          >
            {productsLoading ? "..." : "Actualizar"}
          </button>
        </div>

        {showCreateProduct && (
          <CreateProductForm
            subjectKey={selectedSubject}
            onProductCreated={() => {
              setShowCreateProduct(false);
              loadProducts(selectedSubject);
            }}
            onCancel={() => setShowCreateProduct(false)}
          />
        )}

        {error && <p className="panel-error">{error}</p>}

        {productsLoading ? (
          <p>Cargando {domainLabels.products.toLowerCase()}...</p>
        ) : products.length === 0 ? (
          <p className="empty-state">
            Este {domainLabels.subject.toLowerCase()} no tiene{" "}
            {domainLabels.products.toLowerCase()} registrados.
            <br />
            <button
              className="admin-button"
              onClick={() => setShowCreateProduct(true)}
            >
              Crear primer {domainLabels.product.toLowerCase()}
            </button>
          </p>
        ) : (
          <div className="products-table-container">
            <table className="products-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Tipo</th>
                  <th>Identificador</th>
                  <th>Estado</th>
                  <th>Fecha apertura</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <ProductRow
                    key={p.id}
                    product={p}
                    onRefresh={() => loadProducts(selectedSubject)}
                    onViewTransactions={setViewingProduct}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    );
  }

  // Main view: subject list
  return (
    <section className="panel-section transactional-panel">
      <h2>{domainLabels.transactionalPanelTitle}</h2>
      <p className="panel-description">
        {domainLabels.transactionalPanelDescription}
      </p>

      <div className="subjects-toolbar">
        <label>
          Estado:
          <select
            value={subjectFilter}
            onChange={(e) => setSubjectFilter(e.target.value)}
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
        </label>

        <button
          className="admin-button"
          onClick={loadSubjects}
          disabled={subjectsLoading}
        >
          {subjectsLoading ? "Cargando..." : "Actualizar"}
        </button>

        <span className="subject-count">
          {subjects.length} {domainLabels.subjects.toLowerCase()}
        </span>
      </div>

      {error && <p className="panel-error">{error}</p>}

      {subjectsLoading ? (
        <p>{domainLabels.loadingSubjects}</p>
      ) : subjects.length === 0 ? (
        <p className="empty-state">{domainLabels.noSubjectsFound}</p>
      ) : (
        <div className="subjects-table-container">
          <table className="subjects-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Subject Key</th>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th>{domainLabels.products}</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => (
                <tr
                  key={s.id}
                  className={`subject-row ${
                    s.status !== "active" ? "inactive" : ""
                  }`}
                >
                  <td>{s.id}</td>
                  <td className="subject-key">{s.subject_key}</td>
                  <td>{s.display_name}</td>
                  <td>{s.subject_type}</td>
                  <td>
                    <span className={`badge status-${s.status}`}>
                      {s.status}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        s.product_count > 0 ? "has-products" : "no-products"
                      }`}
                    >
                      {s.product_count}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn-small btn-view"
                      onClick={() => handleSelectSubject(s.subject_key)}
                    >
                      Ver {domainLabels.products.toLowerCase()}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};
