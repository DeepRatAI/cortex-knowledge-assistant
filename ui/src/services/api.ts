export interface QueryCitation {
  id: string;
  source: string;
}

export interface QueryResponse {
  answer: string;
  citations: QueryCitation[];
  max_pii_sensitivity?: string | null;
}

export interface QueryOptions {
  subjectId?: string | null;
  // Context type for filtering documents:
  // - "public_docs": Institutional documentation only (calendario, carreras, etc.)
  // - "educational": Educational material only (textbooks)
  // - undefined/null: All public documents (default when subject is selected)
  contextType?: string | null;
}

// =============================================================================
// SYSTEM STATUS AND SETUP TYPES
// =============================================================================

export interface SystemStatusDatabase {
  initialized: boolean;
  has_admin: boolean;
  admin_count: number;
  user_count: number;
  subject_count: number;
}

export interface SystemStatusQdrant {
  reachable: boolean;
  collection_exists: boolean;
  document_count: number;
}

export interface SystemStatusLLM {
  provider: string;
  healthy: boolean;
}

export interface SystemStatusSystem {
  first_run: boolean;
  ready_for_queries: boolean;
}

export interface SystemStatus {
  database: SystemStatusDatabase;
  qdrant: SystemStatusQdrant;
  llm: SystemStatusLLM;
  system: SystemStatusSystem;
  errors: string[] | null;
}

export interface CreateAdminRequest {
  username: string;
  password: string;
  display_name?: string;
}

export interface CreateAdminResponse {
  success: boolean;
  message: string;
  user_id?: number;
  username?: string;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  user_type: "customer" | "employee";
  role: string;
  display_name?: string;
  dlp_level?: "standard" | "privileged";
  can_access_all_subjects?: boolean;
  subject_ids?: string[];
  // Personal data fields (for Subject record in transactional DB)
  full_name?: string;
  document_id?: string; // DNI, SSN, NIF, etc.
  tax_id?: string; // CUIL/CUIT, NIF, EIN, etc.
  email?: string;
  phone?: string;
}

// =============================================================================
// ORIGINAL TYPES
// =============================================================================

export interface SubjectSummary {
  subject_id: string;
  subject_type: string;
  display_name: string;
  status: string;
}

export interface SubjectDetail extends SubjectSummary {
  attributes?: Record<string, unknown> | null;
}

export interface SubjectServiceSummary {
  service_type: string;
  service_key: string;
  display_name: string;
  status: string;
  metadata?: Record<string, unknown> | null;
}

export interface ProductSnapshot {
  service_type: string;
  service_key: string;
  status: string;
  extra?: Record<string, unknown> | null;
}

export interface TransactionSnapshot {
  timestamp: string;
  transaction_type: string;
  amount: number;
  currency: string;
  description?: string | null;
  extra?: Record<string, unknown> | null;
}

export interface CustomerSnapshot {
  subject_key: string;
  products: ProductSnapshot[];
  recent_transactions: TransactionSnapshot[];
}

export interface AuditLogEntry {
  id: number;
  user_id: string | null;
  username: string | null;
  subject_key: string | null;
  operation: string;
  outcome: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface LoadDemoTransactionsResponse {
  status: string;
  service_instances_created: number;
  transactions_created: number;
  subjects_skipped: number;
}

// API base URL: empty for production (uses nginx proxy), or localhost for development
const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL ?? "";

let currentToken: string | null = null;

export function setAuthToken(token: string | null) {
  currentToken = token;
}

export async function queryBackend(
  question: string,
  options: QueryOptions = {}
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: JSON.stringify({
      query: question,
      ...(options.subjectId ? { subject_id: options.subjectId } : {}),
      ...(options.contextType ? { context_type: options.contextType } : {}),
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }

  const data = await res.json();
  return data as QueryResponse;
}

/**
 * Stream a query response token by token using Server-Sent Events.
 * @param question The user's question
 * @param options Query options including subjectId and contextType
 * @param onToken Callback called for each token received
 * @param onDone Callback called when streaming is complete
 * @param onError Callback called on error
 */
export async function queryBackendStream(
  question: string,
  options: QueryOptions = {},
  onToken: (token: string) => void,
  onDone?: () => void,
  onError?: (error: string) => void
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/query/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: JSON.stringify({
      query: question,
      ...(options.subjectId ? { subject_id: options.subjectId } : {}),
      ...(options.contextType ? { context_type: options.contextType } : {}),
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const dataStr = line.slice(6);
        try {
          const data = JSON.parse(dataStr);
          if (data.token) {
            onToken(data.token);
          }
          if (data.done) {
            onDone?.();
            return;
          }
          if (data.error) {
            onError?.(data.error);
            return;
          }
        } catch {
          // Ignore parse errors
        }
      }
    }
  }

  onDone?.();
}

export async function listSubjects(): Promise<SubjectSummary[]> {
  const res = await fetch(`${API_BASE_URL}/subjects`, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as SubjectSummary[];
}

export async function getSubjectDetail(
  subjectId: string
): Promise<SubjectDetail> {
  const res = await fetch(
    `${API_BASE_URL}/subjects/${encodeURIComponent(subjectId)}`,
    {
      headers: {
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as SubjectDetail;
}

export async function listSubjectServices(
  subjectId: string
): Promise<SubjectServiceSummary[]> {
  const res = await fetch(
    `${API_BASE_URL}/subjects/${encodeURIComponent(subjectId)}/services`,
    {
      headers: {
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as SubjectServiceSummary[];
}

export async function getMySnapshot(): Promise<CustomerSnapshot> {
  const res = await fetch(`${API_BASE_URL}/me/snapshot`, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as CustomerSnapshot;
}

export async function getCustomerSnapshot(
  subjectId: string
): Promise<CustomerSnapshot> {
  const res = await fetch(
    `${API_BASE_URL}/customers/${encodeURIComponent(subjectId)}/snapshot`,
    {
      headers: {
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as CustomerSnapshot;
}

export async function listAuditLog(): Promise<AuditLogEntry[]> {
  const res = await fetch(`${API_BASE_URL}/admin/audit-log`, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as AuditLogEntry[];
}

export async function refreshPublicDocs(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/refresh-public-docs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as { status: string };
}

export async function loadDemoTransactions(): Promise<LoadDemoTransactionsResponse> {
  const res = await fetch(`${API_BASE_URL}/admin/load-demo-transactions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  const data = await res.json();
  return data as LoadDemoTransactionsResponse;
}

// =============================================================================
// SYSTEM STATUS AND SETUP FUNCTIONS
// =============================================================================

/**
 * Get system status (unauthenticated - for setup wizard)
 */
export async function getSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE_URL}/api/system/status`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  return (await res.json()) as SystemStatus;
}

/**
 * Create initial admin user during first-run setup (unauthenticated)
 */
export async function createInitialAdmin(
  data: CreateAdminRequest
): Promise<CreateAdminResponse> {
  const res = await fetch(`${API_BASE_URL}/api/setup/create-admin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as CreateAdminResponse;
}

/**
 * Create a new user (admin only)
 */
export async function createUser(
  data: CreateUserRequest
): Promise<CreateAdminResponse> {
  const res = await fetch(`${API_BASE_URL}/api/admin/users`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as CreateAdminResponse;
}

/**
 * Initialize Qdrant collection (admin only)
 */
export async function initQdrantCollection(): Promise<{
  status: string;
  message: string;
}> {
  const res = await fetch(`${API_BASE_URL}/api/system/init-qdrant`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as { status: string; message: string };
}

// =============================================================================
// ADMIN USER MANAGEMENT FUNCTIONS
// =============================================================================

export interface AdminUserInfo {
  id: number;
  username: string;
  display_name?: string;
  user_type: "customer" | "employee";
  role: string;
  dlp_level: "standard" | "privileged";
  status: "active" | "inactive";
  is_active: boolean;
  can_access_all_subjects: boolean;
  subject_ids: string[];
}

export interface UpdateUserRequest {
  display_name?: string;
  role?: string;
  dlp_level?: "standard" | "privileged";
  status?: "active" | "inactive";
  is_active?: boolean;
  can_access_all_subjects?: boolean;
  new_password?: string;
}

export interface AdminActionResponse {
  success: boolean;
  message: string;
  user_id?: number;
  username?: string;
}

/**
 * List all users (admin only)
 */
export async function listUsers(): Promise<AdminUserInfo[]> {
  const res = await fetch(`${API_BASE_URL}/api/admin/users`, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  const data = await res.json();
  return data.users as AdminUserInfo[];
}

/**
 * Get a single user by ID (admin only)
 */
export async function getUser(userId: number): Promise<AdminUserInfo> {
  const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}`, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as AdminUserInfo;
}

/**
 * Update a user (admin only)
 */
export async function updateUser(
  userId: number,
  data: UpdateUserRequest
): Promise<AdminActionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as AdminActionResponse;
}

/**
 * Delete (deactivate) a user (admin only)
 */
export async function deleteUser(userId: number): Promise<AdminActionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}`, {
    method: "DELETE",
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as AdminActionResponse;
}

// =============================================================================
// TRANSACTIONAL DATA MANAGEMENT (Admin)
// =============================================================================

export interface AdminSubjectSummary {
  id: number;
  subject_key: string;
  subject_type: string;
  display_name: string;
  status: string;
  product_count: number;
}

export interface AdminSubjectListResponse {
  subjects: AdminSubjectSummary[];
  total: number;
}

export interface ServiceInstanceCreate {
  service_type: string;
  service_key: string;
  status?: string;
  extra_metadata?: Record<string, unknown>;
}

export interface ServiceInstanceUpdate {
  service_type?: string;
  service_key?: string;
  status?: string;
  extra_metadata?: Record<string, unknown>;
}

export interface ServiceInstanceResponse {
  id: number;
  subject_id: number;
  subject_key: string;
  service_type: string;
  service_key: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
  extra_metadata: Record<string, unknown> | null;
}

export interface ServiceInstanceListResponse {
  products: ServiceInstanceResponse[];
  total: number;
}

export interface TransactionCreate {
  transaction_type: string;
  amount: number;
  currency?: string;
  description?: string;
  extra_metadata?: Record<string, unknown>;
}

export interface TransactionUpdate {
  transaction_type?: string;
  amount?: number;
  currency?: string;
  description?: string;
  extra_metadata?: Record<string, unknown>;
}

export interface TransactionResponse {
  id: number;
  service_instance_id: number;
  timestamp: string;
  transaction_type: string;
  amount: number;
  currency: string;
  description: string | null;
  extra_metadata: Record<string, unknown> | null;
}

export interface TransactionListResponse {
  transactions: TransactionResponse[];
  total: number;
  product_info: ServiceInstanceResponse | null;
}

/**
 * List all subjects with product counts (admin only)
 */
export async function adminListSubjects(
  statusFilter?: string
): Promise<AdminSubjectListResponse> {
  const params = new URLSearchParams();
  if (statusFilter && statusFilter !== "all") {
    params.set("status_filter", statusFilter);
  }
  const url = `${API_BASE_URL}/api/admin/subjects${
    params.toString() ? `?${params.toString()}` : ""
  }`;
  const res = await fetch(url, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as AdminSubjectListResponse;
}

/**
 * List products for a subject (admin only)
 */
export async function adminListProducts(
  subjectKey: string,
  statusFilter?: string
): Promise<ServiceInstanceListResponse> {
  const params = new URLSearchParams();
  if (statusFilter && statusFilter !== "all") {
    params.set("status_filter", statusFilter);
  }
  const url = `${API_BASE_URL}/api/admin/subjects/${encodeURIComponent(
    subjectKey
  )}/products${params.toString() ? `?${params.toString()}` : ""}`;
  const res = await fetch(url, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as ServiceInstanceListResponse;
}

/**
 * Create a new product for a subject (admin only)
 */
export async function adminCreateProduct(
  subjectKey: string,
  data: ServiceInstanceCreate
): Promise<ServiceInstanceResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/subjects/${encodeURIComponent(
      subjectKey
    )}/products`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as ServiceInstanceResponse;
}

/**
 * Update a product (admin only)
 */
export async function adminUpdateProduct(
  productId: number,
  data: ServiceInstanceUpdate
): Promise<ServiceInstanceResponse> {
  const res = await fetch(`${API_BASE_URL}/api/admin/products/${productId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as ServiceInstanceResponse;
}

/**
 * Delete or deactivate a product (admin only)
 */
export async function adminDeleteProduct(
  productId: number,
  hardDelete: boolean = false
): Promise<AdminActionResponse> {
  const params = hardDelete ? "?hard_delete=true" : "";
  const res = await fetch(
    `${API_BASE_URL}/api/admin/products/${productId}${params}`,
    {
      method: "DELETE",
      headers: {
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as AdminActionResponse;
}

/**
 * List transactions for a product (admin only)
 */
export async function adminListTransactions(
  productId: number,
  options: { limit?: number; offset?: number; txType?: string } = {}
): Promise<TransactionListResponse> {
  const params = new URLSearchParams();
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));
  if (options.txType) params.set("tx_type", options.txType);
  const url = `${API_BASE_URL}/api/admin/products/${productId}/transactions${
    params.toString() ? `?${params.toString()}` : ""
  }`;
  const res = await fetch(url, {
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as TransactionListResponse;
}

/**
 * Create a new transaction for a product (admin only)
 */
export async function adminCreateTransaction(
  productId: number,
  data: TransactionCreate
): Promise<TransactionResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/products/${productId}/transactions`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as TransactionResponse;
}

/**
 * Update a transaction (admin only)
 */
export async function adminUpdateTransaction(
  transactionId: number,
  data: TransactionUpdate
): Promise<TransactionResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/transactions/${transactionId}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as TransactionResponse;
}

/**
 * Delete a transaction (admin only)
 */
export async function adminDeleteTransaction(
  transactionId: number
): Promise<AdminActionResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/transactions/${transactionId}`,
    {
      method: "DELETE",
      headers: {
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as AdminActionResponse;
}

// =============================================================================
// SUBJECT DATA ADMINISTRATION (Auditable CRUD)
// =============================================================================

export interface SubjectDataResponse {
  subject_key: string;
  subject_type: string | null;
  display_name: string | null;
  status: string | null;
  full_name: string | null;
  document_id: string | null;
  tax_id: string | null;
  email: string | null;
  phone: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SubjectUpdateRequest {
  display_name?: string;
  full_name?: string;
  document_id?: string;
  tax_id?: string;
  email?: string;
  phone?: string;
  status?: string;
  subject_type?: string;
  reason: string; // Required - justification for the change
}

export interface SubjectUpdateResponse {
  success: boolean;
  message: string;
  subject_key: string | null;
  changes_count: number;
  audit_id: number | null;
}

export interface SubjectHistoryEntry {
  audit_id: number;
  timestamp: string;
  operator_user_id: string | null;
  operator_username: string | null;
  change_reason: string;
  fields_changed: Record<string, unknown>;
  outcome: string;
  details: Record<string, unknown> | null;
}

export interface DocumentUploadResponse {
  success: boolean;
  message: string;
  filename: string;
  file_size: number;
  file_hash: string;
  audit_id: number;
  ingestion_status: string;
  documents_ingested: number;
}

/**
 * Get subject data for editing (admin only)
 */
export async function adminGetSubjectData(
  subjectKey: string
): Promise<SubjectDataResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/subjects/${encodeURIComponent(subjectKey)}/data`,
    {
      headers: {
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as SubjectDataResponse;
}

/**
 * Update subject data with audit trail (admin only)
 */
export async function adminUpdateSubjectData(
  subjectKey: string,
  data: SubjectUpdateRequest
): Promise<SubjectUpdateResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/subjects/${encodeURIComponent(subjectKey)}/data`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as SubjectUpdateResponse;
}

/**
 * Get modification history for a subject (admin only)
 */
export async function adminGetSubjectHistory(
  subjectKey: string,
  limit: number = 50
): Promise<SubjectHistoryEntry[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/admin/subjects/${encodeURIComponent(
      subjectKey
    )}/history?limit=${limit}`,
    {
      headers: {
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as SubjectHistoryEntry[];
}

/**
 * Upload a public documentation file (admin only)
 * @param file - The file to upload
 * @param category - Document category: "public_docs" or "educational"
 */
export async function adminUploadPublicDocument(
  file: File,
  category: "public_docs" | "educational" = "public_docs"
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);

  const res = await fetch(`${API_BASE_URL}/api/admin/upload-public-document`, {
    method: "POST",
    headers: {
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    },
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error ${res.status}`);
  }
  return (await res.json()) as DocumentUploadResponse;
}
