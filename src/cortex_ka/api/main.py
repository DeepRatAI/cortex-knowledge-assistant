"""FastAPI presentation layer for Cortex KA."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import orjson
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from sqlalchemy import text
from starlette.responses import StreamingResponse

from ..application.dlp import enforce_dlp
from ..application.metrics import (
    active_model_info,
    http_request_latency_seconds,
    http_requests_total,
    query_latency_seconds,
    retrieved_chunks,
)
from ..application.rag_service import RAGService
from ..auth.db import login_db_session
from ..auth.jwt_utils import (
    current_user_from_claims,
    decode_access_token,
    issue_access_token,
)
from ..auth.models import (
    AuditLog,
    CurrentUserContext,
    Subject,
    SubjectService,
    User,
    UserSubject,
)
from ..auth.passwords import verify_password
from ..build_info import APP_VERSION, BUILD_TIME_UTC, GIT_SHA
from ..config import settings
from ..demos.scheduler import demo_scheduler
from ..domain.ports import LLMPort
from ..infrastructure.llm_hf import HFLLM  # to be created
from ..infrastructure.memory_cache import InMemoryCache
from ..infrastructure.memory_store import ConversationMemory, RateLimiter
from ..infrastructure.redis_cache import RedisCache
from ..infrastructure.retriever_qdrant import QdrantRetriever
from ..infrastructure.retriever_stub import StubRetriever
from ..logging import logger
from ..scripts.ingest_docs import ingest_single_document
from ..scripts.ingest_pdfs import ingest_banking_pdfs_into_qdrant
from ..system.setup import (
    SetupNotAllowedError,
    UserInfo,
)
from ..system.setup import ValidationError as SetupValidationError
from ..system.setup import (
    create_initial_admin,
    create_user,
    delete_user,
    get_user,
    is_setup_allowed,
    list_users,
    update_user,
)
from ..system.status import SystemStatus, ensure_qdrant_collection, get_system_status
from ..transactions.models import Base as TransactionBase
from ..transactions.models import (
    ServiceInstance,
    ServiceTransaction,
)
from ..transactions.seed_demo import (
    DemoSeedResult,
    seed_demo_transactions_with_metrics,
)
from ..transactions.service import BankingDomainService

app = FastAPI(title="Cortex Knowledge Assistant", version=APP_VERSION)
origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
if not origins:
    origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# STARTUP EVENT: Auto-initialize critical components
# =============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize critical components on application startup.

    This handler:
    1. Ensures the login database schema exists
    2. Attempts to create the Qdrant collection if it doesn't exist

    Failures are logged but do not prevent startup, allowing the system
    to come up in a degraded state where admins can diagnose and fix issues.
    """
    from ..auth.db import init_login_db

    # 1. Initialize login database
    try:
        init_login_db()
        logger.info("startup_login_db_initialized")
    except Exception as exc:
        logger.error("startup_login_db_failed", error=str(exc))

    # 2. Attempt to initialize Qdrant collection
    # This is non-blocking: if Qdrant is not available, the system still starts
    try:
        success = ensure_qdrant_collection()
        if success:
            logger.info("startup_qdrant_collection_ready")
        else:
            logger.warning("startup_qdrant_collection_init_failed")
    except Exception as exc:
        logger.warning("startup_qdrant_init_error", error=str(exc))

    # 3. Start demo reset scheduler if enabled
    # This is for public "first-run" demos with auto-cleanup
    try:
        demo_scheduler.start()
    except Exception as exc:
        logger.warning("startup_demo_scheduler_failed", error=str(exc))


# Tracing (optional): enable via CKA_ENABLE_TRACING=true
if os.getenv("CKA_ENABLE_TRACING", "").lower() in {
    "1",
    "true",
    "yes",
}:  # pragma: no cover
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    exporter = OTLPSpanExporter()  # Exports to OTLP endpoint (defaults to env vars)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def https_security_headers(request: Request, call_next):  # pragma: no cover
    response = await call_next(request)
    https_flag = settings.https_enabled or os.getenv("CKA_HTTPS_ENABLED", "").lower() in {"1", "true", "yes"}
    if https_flag:
        # HSTS (only under HTTPS)
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
        # CSP
        response.headers.setdefault("Content-Security-Policy", settings.csp_policy)
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):  # pragma: no cover
    """Add basic security headers to responses.
    from ..transactions.service import BankingDomainService

        Note: In production behind TLS/ingress, consider HSTS and stricter CSP.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):  # pragma: no cover
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = req_id
    start = time.perf_counter()
    path = request.url.path
    method = request.method
    # Capture basic caller fingerprint for observability; do not treat it as a
    # strong identity signal.
    client_host = request.client.host if request.client else "unknown"

    logger.info(
        "http_request_start",
        request_id=req_id,
        path=path,
        method=method,
        client_host=client_host,
    )

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:  # Capture unhandled errors for metrics
        status_code = 500
        logger.error(
            "http_request_exception",
            request_id=req_id,
            path=path,
            method=method,
            status_code=status_code,
            error=str(exc),
        )
        raise exc
    finally:
        elapsed = time.perf_counter() - start
        # status class e.g. 2xx
        status_class = f"{status_code // 100}xx"
        http_requests_total.labels(endpoint=path, status_class=status_class).inc()
        http_request_latency_seconds.labels(endpoint=path).observe(elapsed)
        logger.info(
            "http_request_end",
            request_id=req_id,
            path=path,
            method=method,
            status_code=status_code,
            elapsed_seconds=elapsed,
        )
    response.headers["X-Request-ID"] = req_id
    return response


class QueryRequest(BaseModel):
    """Incoming query payload."""

    query: str
    session_id: str | None = None
    # Optional subject identifier used as an *intention* by authenticated
    # users. The backend remains the sole authority and will only honour
    # this when it is consistent with the CurrentUser context.
    subject_id: str | None = None
    # Context type for filtering documents:
    # - "public_docs": Institutional documentation only (calendario, carreras, etc.) - NO textbooks
    # - "educational": Educational material only (textbooks, academic PDFs)
    # - None: All public documents (default behavior when subject_id is null)
    context_type: str | None = None


class QueryResponse(BaseModel):
    """Outgoing answer structure."""

    answer: str
    used_chunks: list[str]
    session_id: str | None = None
    citations: list[dict] | None = None


class AuditLogEntry(BaseModel):
    """External view of an audit log entry for admin consumption."""

    id: int
    user_id: str | None = None
    username: str | None = None
    subject_key: str | None = None
    operation: str
    outcome: str
    details: dict | None = None
    created_at: str


class LoginRequest(BaseModel):
    """Username/password login request.

    This endpoint is intended for controlled demo environments. In a
    production deployment, authentication would typically be delegated to an
    external IdP/OIDC provider, and this endpoint would either be removed or
    limited to service accounts.
    """

    username: str
    password: str


class LoginUserInfo(BaseModel):
    id: str
    username: str
    user_type: str
    role: str
    dlp_level: str
    can_access_all_subjects: bool
    subject_ids: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: LoginUserInfo


class SubjectSummary(BaseModel):
    """Summary view of a subject/entity accessible to the current user."""

    subject_id: str
    subject_type: str
    display_name: str
    status: str


class SubjectDetail(SubjectSummary):
    """Detailed view of a subject including domain-specific attributes."""

    attributes: dict | None = None


class SubjectServiceSummary(BaseModel):
    """Summary of a service/product attached to a subject."""

    service_type: str
    service_key: str
    display_name: str
    status: str
    metadata: dict | None = None

    class Config:
        from_attributes = True


class ProductSummary(BaseModel):
    """External view of a product/service instance for the banking demo."""

    service_type: str
    service_key: str
    status: str
    extra: dict | None = None


class TransactionSummary(BaseModel):
    """External view of a transactional movement for the banking demo."""

    timestamp: str
    transaction_type: str
    amount: float
    currency: str
    description: str | None = None
    extra: dict | None = None


class CustomerSnapshotDTO(BaseModel):
    """Snapshot of products and recent transactions for a customer.

    Personal data fields (display_name, document_id, etc.) are
    PRE-MASKED according to the viewer's role before being returned.
    See pii_masking.py for the masking logic.
    """

    subject_key: str
    products: list[ProductSummary]
    recent_transactions: list[TransactionSummary]
    # Personal data fields - PRE-MASKED by pii_masking
    display_name: str | None = None
    document_id: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None


class _FakeLLM(LLMPort):
    """Simple deterministic LLM used for tests to avoid external dependency."""

    def generate(self, prompt: str) -> str:  # type: ignore[override]
        _ = prompt  # acknowledge param
        return "This is a synthesized answer based on internal procedures."


class CurrentUser(BaseModel):
    """Authenticated user context used for authorization decisions.

    In a real deployment this would be populated from a JWT/OIDC token or
    an identity provider. For this demo, we keep an in-memory mapping from
    redacted_answer = enforce_dlp(answer_obj.answer, user=current_user)
    access control.

    The ``dlp_level`` field is a coarse-grained hint for DLP behaviour:

    - "standard": default level; full DLP redaction is applied.
    - "privileged": callers are trusted to handle PII and may see
        unredacted answers (for example, internal backoffice tools in a
        tightly controlled network).

    Backends integrating with a real IdP can derive this from roles or
    claims (e.g. "role=backoffice" or specific entitlements).
    """

    user_id: str
    allowed_subject_ids: list[str]
    dlp_level: str = "standard"
    user_type: str = "customer"
    role: str | None = None
    can_access_all_subjects: bool = False


_DEMO_USER_MAP: dict[str, CurrentUser] = {
    # Example: API key "demo-key-cli-81093" is bound to customer CLI-81093.
    # In production, this should come from an identity provider / IAM system.
    "demo-key-cli-81093": CurrentUser(
        user_id="user-cli-81093",
        allowed_subject_ids=["CLI-81093"],
        dlp_level="standard",
        user_type="customer",
        role="customer",
        can_access_all_subjects=False,
    ),
    # Example of a privileged operator with access to the same subject but
    # with relaxed DLP. This key is provided for demonstration and tests; it
    # should never be used in unconstrained environments.
    "demo-key-cli-81093-ops": CurrentUser(
        user_id="ops-cli-81093",
        allowed_subject_ids=["CLI-81093"],
        dlp_level="privileged",
        user_type="employee",
        role="admin",
        can_access_all_subjects=True,
    ),
}


def _current_user_from_jwt(authorization: str | None) -> CurrentUser | None:
    """Build CurrentUser from a Bearer JWT in the Authorization header.

    This function is intentionally strict: any parsing/validation error
    results in ``None`` so that the caller can fall back to other auth
    mechanisms or return 401. We never partially trust a malformed token.
    """

    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    try:
        claims = decode_access_token(token)
    except Exception:
        # Any JWT error results in authentication failure; do not
        # attempt to infer identity from partial/invalid tokens.
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    ctx = current_user_from_claims(claims)
    # Map enriched context to the API-level CurrentUser model used by the
    # rest of the codebase, preserving user_type and
    # can_access_all_subjects so that endpoints like /query can enforce
    # multi-tenant rules for employees/admins.
    return CurrentUser(
        user_id=ctx.user_id,
        allowed_subject_ids=ctx.subject_ids,
        dlp_level=ctx.dlp_level,
        user_type=ctx.user_type,
        role=ctx.role,
        can_access_all_subjects=ctx.can_access_all_subjects,
    )


def get_current_user(
    x_cka_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """Authenticate request and return current user context.

    Precedence:
    1. If an Authorization: Bearer <token> header is present, we validate the
       JWT and derive identity from its claims.
    2. Otherwise, we fall back to the existing API key demo mechanism.

    This allows a smooth transition where UI clients can migrate to JWT-based
    auth without breaking local dev scripts that still rely on x-cka-api-key.
    """

    # 1) Prefer JWT Bearer token when present.
    if authorization:
        return _current_user_from_jwt(authorization)

    # 2) Optional fallback: legacy API key-based demo authentication.
    #
    # This is *not* intended for production. Gate it behind an explicit
    # environment flag so that real deployments rely solely on JWT/OIDC.
    demo_api_key_enabled = os.getenv("CKA_ENABLE_DEMO_API_KEY", "true").lower() in {
        "1",
        "true",
        "yes",
    }

    if not demo_api_key_enabled:
        # No JWT and demo API key disabled: treat as unauthenticated.
        raise HTTPException(status_code=401, detail="Missing or invalid credentials")

    configured_api_key = os.getenv("CKA_API_KEY") or settings.api_key
    if configured_api_key and x_cka_api_key != configured_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not x_cka_api_key or x_cka_api_key not in _DEMO_USER_MAP:
        raise HTTPException(status_code=403, detail="Forbidden")
    return _DEMO_USER_MAP[x_cka_api_key]


@app.get(
    "/subjects/{subject_id}/services",
    response_model=list[SubjectServiceSummary],
    name="List services for a subject",
)
def list_subject_services(
    subject_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return transactional services/products attached to a subject.

    Access control mirrors :func:`get_subject_detail`: employees with
    ``can_access_all_subjects`` can see any subject; other callers must
    be explicitly linked to the subject via ``UserSubject``.
    """

    with login_db_session() as db:
        subject = db.query(Subject).filter(Subject.subject_key == subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        if not current_user.can_access_all_subjects:
            link = (
                db.query(UserSubject)
                .filter(
                    UserSubject.user_id == int(current_user.user_id),
                    UserSubject.subject_id == subject_id,
                )
                .first()
            )
            if not link:
                raise HTTPException(status_code=403, detail="Not allowed for this subject")

        services = db.query(SubjectService).filter(SubjectService.subject_id == subject.id).all()
        # Map ORM objects to Pydantic models, exposing extra_metadata as metadata.
        return [
            SubjectServiceSummary(
                service_type=s.service_type,
                service_key=s.service_key,
                display_name=s.display_name,
                status=s.status,
                metadata=s.extra_metadata,
            )
            for s in services
        ]


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    """Authenticate a user against the login DB and issue a JWT.

    Security considerations:
    - This endpoint is for demo/evaluation environments; do not expose it
      directly on the internet without rate limiting and additional
      protections (IP allowlists, WAF, etc.).
    - Passwords are always verified via a strong hash (bcrypt via passlib).
    - On failure we return generic 401/403 errors without leaking whether
      the username exists.
    """

    username = payload.username.strip()
    if not username:
        _audit(login_db_session, operation="login", outcome="failure", username="")
        raise HTTPException(status_code=400, detail="Invalid username or password")

    with login_db_session() as db:
        user: User | None = db.query(User).filter(User.username == username).one_or_none()

        if not user:
            # Do a dummy verify to keep timing more uniform and avoid
            # leaking whether the user exists.
            verify_password(payload.password, "$2b$12$invalidsaltinvalidsaltinv.u8nq.Er3x")
            _audit(
                login_db_session,
                operation="login",
                outcome="failure",
                username=username,
                details={"reason": "user_not_found"},
            )
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if user.status != "active":
            _audit(
                login_db_session,
                operation="login",
                outcome="denied",
                user_id=str(user.id),
                username=user.username,
                details={"reason": "user_disabled"},
            )
            raise HTTPException(status_code=403, detail="User is disabled")

        if not verify_password(payload.password, user.password_hash):
            _audit(
                login_db_session,
                operation="login",
                outcome="failure",
                user_id=str(user.id),
                username=user.username,
                details={"reason": "bad_password"},
            )
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Collect subject_ids for this user; employees with
        # can_access_all_subjects=True may legitimately have an empty list.
        subject_rows = db.query(UserSubject.subject_id).filter(UserSubject.user_id == user.id).all()
        subject_ids = [row[0] for row in subject_rows]

        # Build a detached context while the ORM instance is still bound to
        # the session, to avoid DetachedInstanceError later.
        user_ctx = CurrentUserContext.from_orm(user, subject_ids)
        _audit(
            login_db_session,
            operation="login",
            outcome="success",
            user_id=user_ctx.user_id,
            username=user_ctx.username,
            details={"subject_ids": user_ctx.subject_ids},
        )
    token = issue_access_token(user_ctx)

    return LoginResponse(
        access_token=token,
        user=LoginUserInfo(
            id=user_ctx.user_id,
            username=user_ctx.username,
            user_type=user_ctx.user_type,
            role=user_ctx.role,
            dlp_level=user_ctx.dlp_level,
            can_access_all_subjects=user_ctx.can_access_all_subjects,
            subject_ids=user_ctx.subject_ids,
        ),
    )


@app.post("/login", response_model=LoginResponse)
def legacy_login(payload: LoginRequest) -> LoginResponse:
    """Backward-compatible login endpoint.

    Some tests and potential legacy clients still call ``/login`` instead of
    ``/auth/login``. Keep a thin wrapper here that forwards to the main
    :func:`login` implementation so behaviour stays consistent.
    """

    return login(payload)


@app.get("/subjects", response_model=list[SubjectSummary])
def list_subjects(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SubjectSummary]:
    """List subjects/entities accessible to the current user.

    Multi-tenant rules:
    - Customers (user_type == "customer") see only their own subjects as
      derived from allowed_subject_ids.
    - Employees with can_access_all_subjects=True may see all subjects.
    - Employees without global access see only subjects explicitly linked
      via user_subjects.
    """

    user_type = getattr(current_user, "user_type", "customer")
    can_access_all = bool(getattr(current_user, "can_access_all_subjects", False))

    with login_db_session() as db:
        if user_type == "employee" and can_access_all:
            query = db.query(Subject)
        else:
            # Restrict to subjects linked via UserSubject for this user.
            subq = db.query(UserSubject.subject_id).filter(UserSubject.user_id == int(current_user.user_id)).subquery()
            query = db.query(Subject).filter(Subject.subject_key.in_(subq))

        subjects: list[Subject] = query.all()

        # Build DTOs while the session is still open to avoid detached instances.
        summaries: list[SubjectSummary] = [
            SubjectSummary(
                subject_id=s.subject_key,
                subject_type=s.subject_type,
                display_name=s.display_name,
                status=s.status,
            )
            for s in subjects
        ]

    return summaries


@app.get("/subjects/{subject_id}", response_model=SubjectDetail)
def get_subject_detail(subject_id: str, current_user: CurrentUser = Depends(get_current_user)) -> SubjectDetail:
    """Return detailed information for a single subject.

    Access is granted only if the subject is within the caller's allowed
    tenant scope following the same rules as /subjects.
    """

    user_type = getattr(current_user, "user_type", "customer")
    can_access_all = bool(getattr(current_user, "can_access_all_subjects", False))

    with login_db_session() as db:
        subject: Subject | None = db.query(Subject).filter(Subject.subject_key == subject_id).one_or_none()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        if not (user_type == "employee" and can_access_all):
            # Enforce that the subject is actually linked to this user.
            link = (
                db.query(UserSubject)
                .filter(
                    UserSubject.user_id == int(current_user.user_id),
                    UserSubject.subject_id == subject.subject_key,
                )
                .one_or_none()
            )
            if not link:
                raise HTTPException(status_code=403, detail="Forbidden")

        # Build the detail DTO while the session is still open to avoid
        # accessing ORM attributes on a detached instance.
        detail = SubjectDetail(
            subject_id=subject.subject_key,
            subject_type=subject.subject_type,
            display_name=subject.display_name,
            status=subject.status,
            attributes=subject.attributes,
        )

    return detail


def _select_llm():
    provider = os.getenv("CKA_LLM_PROVIDER", settings.llm_provider).strip()
    # In confidential retrieval mode we forbid Fake LLMs and require a
    # real provider (currently HF). This is a hard guardrail intended for
    # banking-like deployments: running with Fake while this flag is true
    # is considered a configuration error.
    if settings.confidential_retrieval_only and provider.lower() == "fake":
        raise RuntimeError(
            "confidential_retrieval_only is enabled but llm_provider is 'Fake'. "
            "Please configure a real provider (e.g. HF)."
        )

    if provider.lower() == "hf":
        key = os.getenv("HF_API_KEY") or settings.hf_api_key
        if not key:
            # No key available: gracefully fallback to Fake for dev
            (logger if isinstance(logger, object) else None)
            return _FakeLLM()
        return HFLLM(api_key=key, model=os.getenv("CKA_HF_MODEL") or settings.hf_model)
    # default: Fake
    return _FakeLLM()


def _select_retriever():
    if os.getenv("CKA_USE_QDRANT", "").lower() in {"1", "true", "yes"}:
        return QdrantRetriever()
    return StubRetriever()


def _audit(
    db_session_factory,
    *,
    operation: str,
    outcome: str = "success",
    user_id: str | None = None,
    username: str | None = None,
    subject_key: str | None = None,
    details: dict | None = None,
) -> None:
    """Best-effort audit log writer.

    This helper is deliberately defensive: any failure while writing audit
    information is logged but never breaks the main control flow. It uses
    the same login DB as the identity tables so that operators can query a
    single place for security-relevant events.
    """

    try:
        with db_session_factory() as db:
            entry = AuditLog(
                user_id=str(user_id) if user_id is not None else None,
                username=username,
                subject_key=subject_key,
                operation=operation,
                outcome=outcome,
                details=details or None,
            )
            db.add(entry)
            # Rely on context manager for commit/rollback semantics.
    except Exception:  # pragma: no cover - audit failures must not break flow
        logger.exception("audit_log_write_failed", op=operation)


# Instantiate service after evaluating environment flags; this allows tests to set
# env vars prior to import or reloading without triggering external connections.
_cache = InMemoryCache()
if os.getenv("CKA_USE_REDIS", "").lower() in {"1", "true", "yes"}:
    try:  # pragma: no cover - depends on external service
        _cache = RedisCache()
    except Exception:
        _cache = InMemoryCache()

_banking_domain_service = BankingDomainService()

_service = RAGService(
    retriever=_select_retriever(),
    llm=_FakeLLM() if "PYTEST_CURRENT_TEST" in os.environ else _select_llm(),
    cache=_cache,
)
_rate_limiter = RateLimiter(settings.rate_limit_qpm)
_memory = ConversationMemory(settings.conversation_max_turns)


@app.post("/query", response_model=QueryResponse)
def query_rag(
    payload: QueryRequest,
    x_cka_api_key: str | None = Header(default=None),
    _x_cka_subject_id: str | None = Header(default=None),  # deprecated for security
    current_user: CurrentUser = Depends(get_current_user),
    request: Request = None,
) -> QueryResponse:
    """Handle a RAG query and return an answer.

    Args:
        payload: QueryRequest with the user question.
    Returns:
        QueryResponse containing generated answer and chunk IDs.
    """
    # Input validation: length and basic sanitization
    q = (payload.query or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail="Query must not be empty")
    if len(q) > 2000:
        raise HTTPException(status_code=413, detail="Query too long")

    # Ensure we have an authenticated principal. get_current_user() will already
    # have enforced JWT / legacy API key rules, but if authentication was
    # explicitly disabled or misconfigured we fail closed here instead of
    # raising attribute errors deeper in the flow.
    if current_user is None:  # type: ignore[truthy-function]
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Establish session id first (used for keyed rate limiting)
    session_id = payload.session_id or "default"
    # Rate limiting: keyed by API key if present else session id
    limiter_key = x_cka_api_key or session_id or "global"
    if not _rate_limiter.allow(key=limiter_key):
        # Consistent body and Retry-After
        retry_after = 1
        try:
            retry_after = getattr(_rate_limiter, "retry_after", lambda k: 1)(limiter_key)
        except Exception:
            pass
        headers = {"Retry-After": str(retry_after)}
        raise HTTPException(status_code=429, detail="rate_limited", headers=headers)

    # If tests or runtime toggled fake flag post-start, refresh LLM.
    if os.getenv("CKA_FAKE_LLM", "").lower() in {"1", "true", "yes"}:
        _service._llm = _FakeLLM()  # type: ignore[attr-defined]

    # Preserve the original query for memory storage (avoid exponential context growth)
    original_query = payload.query

    # Optionally enrich with conversation context (append last turns)
    # This enriched version is used only for the LLM, NOT stored in memory.
    history = _memory.history(session_id)
    enriched_query = original_query
    if history:
        # Lightweight augmentation: prepend previous Q/A as bullets
        past = "\n".join(f"- Q: {q}\n- A: {a}" for q, a in history)
        enriched_query = f"Previous context (most recent first):\n{past}\n\nCurrent question: {original_query}"

    start = time.perf_counter()

    # Resolve the effective subject_id for this request following strict
    # multi-tenant rules:
    #
    # EMPLOYEES / ADMINS (user_type == "employee"):
    #   - Con can_access_all_subjects=True pueden consultar:
    #     a) Sin subject_id -> solo documentación pública (PDFs, FAQs)
    #     b) Con subject_id -> docs públicos + privados del cliente indicado
    #   - Sin can_access_all_subjects solo pueden usar subject_ids asignados.
    #
    # CUSTOMERS (user_type == "customer"):
    #   - Solo pueden operar sobre sus propios allowed_subject_ids.
    #   - Si tienen múltiples, se usa el primero salvo que especifiquen uno válido.
    #   - SIEMPRE requieren un subject_id (no pueden consultar sin contexto).
    #
    # SEGURIDAD: subject_id se resuelve server-side, nunca se confía
    # directamente en el input del cliente para evitar tenant-breakout.
    requested_subject = payload.subject_id
    user_type = getattr(current_user, "user_type", "customer")
    can_access_all = bool(getattr(current_user, "can_access_all_subjects", False))

    if user_type == "employee":
        if can_access_all:
            # Admins/empleados privilegiados: subject_id OPCIONAL.
            # - None -> consulta solo documentación pública
            # - Valor -> consulta pública + privada del cliente
            subject_id = requested_subject  # puede ser None, eso es válido
        else:
            # Empleado sin acceso global: debe usar uno de sus subject_ids asignados
            if not current_user.allowed_subject_ids:
                raise HTTPException(status_code=403, detail="No customer scope assigned")
            if requested_subject and requested_subject in current_user.allowed_subject_ids:
                subject_id = requested_subject
            else:
                subject_id = current_user.allowed_subject_ids[0]
    else:
        # Customer: DEBE tener y usar un subject_id de su lista
        if not current_user.allowed_subject_ids:
            raise HTTPException(status_code=403, detail="No customer scope assigned")
        if requested_subject and requested_subject in current_user.allowed_subject_ids:
            subject_id = requested_subject
        else:
            subject_id = current_user.allowed_subject_ids[0]

    # Optionally enrich with transactional snapshot when a subject is in scope.
    customer_snapshot = None
    if subject_id:
        try:
            # For university domain, get more transactions to include all grades
            demo_domain = os.environ.get("CKA_DEMO_DOMAIN", "banking").lower()
            max_txs = 50 if demo_domain == "university" else 20

            # Determine if this is the user's own data (for PII visibility)
            # A customer viewing their own subject gets full unmasked data.
            # Employees see masked data; admins see full data.
            is_own_data = current_user.user_type == "customer" and subject_id in current_user.allowed_subject_ids
            viewer_role = current_user.role or current_user.user_type or "employee"

            customer_snapshot = _banking_domain_service.get_customer_snapshot(
                subject_key=subject_id,
                max_transactions=max_txs,
                viewer_role=viewer_role,
                is_own_data=is_own_data,
            )
            # Audit PII access when personal data is exposed to LLM context
            if customer_snapshot and customer_snapshot.display_name:
                _audit(
                    login_db_session,
                    operation="pii_access",
                    outcome="success",
                    user_id=current_user.user_id,
                    username=getattr(current_user, "role", None),
                    subject_key=subject_id,
                    details={
                        "viewer_role": viewer_role,
                        "is_own_data": is_own_data,
                        "pii_fields_exposed": [
                            f
                            for f in [
                                "display_name",
                                "document_id",
                                "tax_id",
                                "email",
                                "phone",
                            ]
                            if getattr(customer_snapshot, f, None)
                        ],
                    },
                )
        except Exception:
            # Never break the main flow if the transactional DB is unavailable.
            logger.exception("banking_snapshot_failed", subject_id=subject_id)

    # Enforce that subject_id always comes from server-side user context and
    # never directly from client headers/body to avoid tenant breakout.
    # Use enriched_query (with conversation history) for the LLM.
    answer_obj = _service.answer(
        enriched_query,
        subject_id=subject_id,
        customer_snapshot=customer_snapshot,
        context_type=payload.context_type,
    )
    # Store only the original query in memory to prevent exponential context growth.
    _memory.add_turn(session_id, original_query, answer_obj.answer)
    duration = time.perf_counter() - start
    req_id = getattr(getattr(request, "state", object()), "request_id", None)
    safe_logger = logger.bind(request_id=req_id) if req_id else logger
    # Log only the query and user id; avoid including raw PII from context.
    safe_logger.info(
        "query_answered",
        query=original_query,  # Log the original, not enriched
        user_id=current_user.user_id,
        subject_id=subject_id,
    )
    _audit(
        login_db_session,
        operation="query",
        outcome="success",
        user_id=current_user.user_id,
        username=getattr(current_user, "role", None),
        subject_key=subject_id,
        details={"duration_sec": duration},
    )
    # Metrics
    query_latency_seconds.observe(duration)
    retrieved_chunks.observe(len(answer_obj.used_chunks))
    # Apply the central DLP facade before returning to clients. Today this
    # delegates to redact_pii, but enforce_dlp is the single governance point
    # for future, stricter policies. It also honours the current_user.dlp_level
    # hint, allowing privileged operators to bypass redaction when explicitly
    # configured.
    redacted_answer = enforce_dlp(answer_obj.answer, user=current_user)
    return QueryResponse(
        answer=redacted_answer,
        used_chunks=answer_obj.used_chunks,
        session_id=session_id,
        citations=answer_obj.citations,
    )


@app.get("/admin/audit-log", response_model=list[AuditLogEntry])
def list_audit_log(
    current_user: CurrentUser = Depends(get_current_user),
    user_id: str | None = None,
    subject_key: str | None = None,
    operation: str | None = None,
    limit: int = 200,
):
    """List recent audit log entries for administrators.

    Access control:
    - Only employees with an administrative role (e.g. "admin") are allowed.
    - Results are ordered by most recent first and limited by `limit`.
    """

    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") in {"admin"}):
        raise HTTPException(status_code=403, detail="Forbidden")

    limit = max(1, min(limit, 1000))

    with login_db_session() as db:
        query = db.query(AuditLog).order_by(AuditLog.created_at.desc())

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if subject_key:
            query = query.filter(AuditLog.subject_key == subject_key)
        if operation:
            query = query.filter(AuditLog.operation == operation)

        rows: list[AuditLog] = query.limit(limit).all()

        # Important: materialize all fields we need *inside* the session to
        # avoid DetachedInstanceError when accessing attributes after the
        # context manager closes the session.
        results: list[AuditLogEntry] = []
        for row in rows:
            created_at = row.created_at.isoformat() if row.created_at else ""
            results.append(
                AuditLogEntry(
                    id=row.id,
                    user_id=row.user_id,
                    username=row.username,
                    subject_key=row.subject_key,
                    operation=row.operation,
                    outcome=row.outcome,
                    details=row.details or None,
                    created_at=created_at,
                )
            )

    return results


@app.get("/me/snapshot", response_model=CustomerSnapshotDTO)
def get_my_snapshot(current_user: CurrentUser = Depends(get_current_user)):
    """Return the banking snapshot for the currently authenticated customer.

    This endpoint is restricted to users of type "customer" and uses the
    first allowed subject as the logical customer id.
    """

    if getattr(current_user, "user_type", "") != "customer":
        raise HTTPException(status_code=403, detail="Forbidden")

    if not current_user.allowed_subject_ids:
        raise HTTPException(status_code=403, detail="No customer scope assigned")

    subject_key = current_user.allowed_subject_ids[0]
    # Customer viewing their own data - no masking needed
    snapshot = _banking_domain_service.get_customer_snapshot(
        subject_key=subject_key,
        viewer_role="customer",
        is_own_data=True,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No transactional data found")

    return CustomerSnapshotDTO(
        subject_key=snapshot.subject_key,
        products=[
            ProductSummary(
                service_type=p.service_type,
                service_key=p.service_key,
                status=p.status,
                extra=p.extra,
            )
            for p in snapshot.products
        ],
        recent_transactions=[
            TransactionSummary(
                timestamp=t.timestamp.isoformat(),
                transaction_type=t.transaction_type,
                amount=t.amount,
                currency=t.currency,
                description=t.description,
                extra=t.extra,
            )
            for t in snapshot.recent_transactions
        ],
        display_name=snapshot.display_name,
        document_id=snapshot.document_id,
        tax_id=snapshot.tax_id,
        email=snapshot.email,
        phone=snapshot.phone,
    )


@app.get("/customers/{subject_key}/snapshot", response_model=CustomerSnapshotDTO)
def get_customer_snapshot(subject_key: str, current_user: CurrentUser = Depends(get_current_user)):
    """Return the banking snapshot for a given subject (employee/admin only)."""

    if getattr(current_user, "user_type", "") != "employee":
        raise HTTPException(status_code=403, detail="Forbidden")

    # Employees must either have global access or explicit subject binding.
    can_access_all = bool(getattr(current_user, "can_access_all_subjects", False))
    if not can_access_all and subject_key not in current_user.allowed_subject_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Employee/admin viewing customer data - apply role-based masking
    viewer_role = current_user.role or "employee"
    snapshot = _banking_domain_service.get_customer_snapshot(
        subject_key=subject_key,
        viewer_role=viewer_role,
        is_own_data=False,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No transactional data found")

    return CustomerSnapshotDTO(
        subject_key=snapshot.subject_key,
        products=[
            ProductSummary(
                service_type=p.service_type,
                service_key=p.service_key,
                status=p.status,
                extra=p.extra,
            )
            for p in snapshot.products
        ],
        recent_transactions=[
            TransactionSummary(
                timestamp=t.timestamp.isoformat(),
                transaction_type=t.transaction_type,
                amount=t.amount,
                currency=t.currency,
                description=t.description,
                extra=t.extra,
            )
            for t in snapshot.recent_transactions
        ],
        display_name=snapshot.display_name,
        document_id=snapshot.document_id,
        tax_id=snapshot.tax_id,
        email=snapshot.email,
        phone=snapshot.phone,
    )


@app.post("/admin/refresh-public-docs")
def refresh_public_docs(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Trigger re-ingestion of public banking PDFs into Qdrant.

    Security and access control:

    - Only employees with the "admin" role are allowed to call this endpoint.
    - The operation is idempotent with respect to document identity: PDFs are
      converted into `IngestDoc` objects with stable `doc_id` keys, and the
      underlying ingestion pipeline performs upserts in Qdrant.

    Data-handling guarantees:

    - Only documents under the public `documentacion/` folder are ingested.
      These emulate public-facing manuals and guides, not customer PII.
    - No `subject_id` or `id_cliente` metadata is attached to these
      documents, so they cannot be used to infer individual customers.
    """

    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") in {"admin"}):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        count = ingest_banking_pdfs_into_qdrant()
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("refresh_public_docs_failed")
        raise HTTPException(status_code=500, detail="Ingest failed") from exc

    return {"status": "ok", "documents_ingested": count}


class LoadDemoTransactionsResponse(BaseModel):
    status: str
    service_instances_created: int
    transactions_created: int
    subjects_skipped: int


@app.post("/admin/load-demo-transactions", response_model=LoadDemoTransactionsResponse)
def load_demo_transactions(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Trigger seeding of synthetic transactional demo data.

    Security and access control:
    - Only employees with the "admin" role are allowed to call this endpoint.

    Behaviour:
    - Idempotent at the level of "subject has data": subjects that already
      have at least one transactional product are skipped.
    - Returns aggregate metrics to help admins understand what changed.
    """

    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") in {"admin"}):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        result: DemoSeedResult = seed_demo_transactions_with_metrics()
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("admin_load_demo_transactions_failed")
        raise HTTPException(status_code=500, detail="Demo transaction seed failed") from exc

    # Record in audit log for traceability.
    _audit(
        login_db_session,
        operation="admin_load_demo_transactions",
        outcome="success",
        user_id=str(current_user.user_id),
        username=None,
        subject_key=None,
        details={
            "service_instances_created": result.service_instances_created,
            "transactions_created": result.transactions_created,
            "subjects_skipped": result.subjects_skipped,
        },
    )

    return LoadDemoTransactionsResponse(
        status="ok",
        service_instances_created=result.service_instances_created,
        transactions_created=result.transactions_created,
        subjects_skipped=result.subjects_skipped,
    )


# =============================================================================
# Health Check Endpoints (Kubernetes-compatible)
# =============================================================================


def _check_database_health() -> tuple[bool, str]:
    """Check PostgreSQL/SQLite database connectivity."""
    try:
        with login_db_session() as session:
            session.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as e:
        return False, f"error: {str(e)[:100]}"


def _check_qdrant_health() -> tuple[bool, str, int]:
    """Check Qdrant vector store connectivity and document count."""
    try:
        if os.getenv("CKA_USE_QDRANT", "").lower() not in {"1", "true", "yes"}:
            return True, "not_configured", 0
        retriever = QdrantRetriever()
        info = retriever._client.get_collection(retriever._collection)
        count = getattr(info, "points_count", 0)
        return True, "connected", count
    except Exception as e:
        return False, f"error: {str(e)[:100]}", 0


def _check_redis_health() -> tuple[bool, str]:
    """Check Redis cache connectivity."""
    try:
        redis_url = os.getenv("REDIS_URL", settings.redis_url if hasattr(settings, "redis_url") else None)
        if not redis_url:
            return True, "not_configured"
        import redis

        client = redis.from_url(redis_url, socket_timeout=2)
        client.ping()
        return True, "connected"
    except Exception as e:
        return False, f"error: {str(e)[:50]}"


def _check_llm_health() -> tuple[bool, str, str | None]:
    """Check LLM provider health."""
    provider = os.getenv("CKA_LLM_PROVIDER", settings.llm_provider).strip().lower()
    if provider != "hf":
        return True, provider, None

    llm = _select_llm()
    try:
        healthy = getattr(llm, "healthy", lambda: False)()
        model = getattr(llm, "model", None)
        return healthy, provider, model
    except Exception:
        return False, provider, None


@app.get("/health")
def health() -> dict:
    """Comprehensive health check endpoint.

    Returns detailed status of all components for monitoring and debugging.
    Always returns 200 to allow load balancers to receive diagnostics.
    """
    # Database
    db_ok, db_status = _check_database_health()

    # Qdrant
    qdrant_ok, qdrant_status, doc_count = _check_qdrant_health()

    # Redis
    redis_ok, redis_status = _check_redis_health()

    # LLM
    llm_ok, llm_provider, llm_model = _check_llm_health()

    # Overall status
    all_ok = db_ok and qdrant_ok and llm_ok

    return {
        "status": "healthy" if all_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": {"healthy": db_ok, "status": db_status},
            "qdrant": {
                "healthy": qdrant_ok,
                "status": qdrant_status,
                "documents": doc_count,
            },
            "redis": {"healthy": redis_ok, "status": redis_status},
            "llm": {"healthy": llm_ok, "provider": llm_provider, "model": llm_model},
        },
    }


@app.get("/live")
def liveness() -> dict:
    """Kubernetes liveness probe.

    Returns 200 if the application is running and can handle requests.
    This should be lightweight - only checks if the process is alive.
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/ready")
def readiness() -> Response:
    """Kubernetes readiness probe.

    Returns 200 if the application is ready to receive traffic.
    Returns 503 if critical dependencies are unavailable.
    """
    # Check critical dependencies
    db_ok, _ = _check_database_health()
    qdrant_ok, _, _ = _check_qdrant_health()
    llm_ok, _, _ = _check_llm_health()

    ready = db_ok and qdrant_ok and llm_ok

    response_data = {
        "ready": ready,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_ok,
            "qdrant": qdrant_ok,
            "llm": llm_ok,
        },
    }

    if ready:
        return Response(
            content=orjson.dumps(response_data),
            media_type="application/json",
            status_code=200,
        )
    else:
        return Response(
            content=orjson.dumps(response_data),
            media_type="application/json",
            status_code=503,
        )


# =============================================================================
# DEMO STATUS ENDPOINT (Read-only, no trigger capability)
# =============================================================================


@app.get("/api/demo/status")
def demo_status() -> dict:
    """Get demo environment status including reset timer.

    This endpoint provides read-only information about the demo environment:
    - Whether auto-reset is enabled
    - Next scheduled reset time
    - Seconds until next reset (for countdown UI)

    Security: This endpoint does NOT provide any way to trigger a reset.
    Resets are only performed by the internal scheduler.
    """
    return demo_scheduler.get_status()


@app.get("/metrics")
def metrics() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.get("/version")
def version() -> dict:
    return {
        "git_sha": GIT_SHA,
        "build_time": BUILD_TIME_UTC,
        "app_version": APP_VERSION,
    }


# =============================================================================
# SYSTEM STATUS AND SETUP ENDPOINTS
# =============================================================================


class SystemStatusResponse(BaseModel):
    """Response model for system status endpoint."""

    database: dict
    qdrant: dict
    llm: dict
    system: dict
    errors: list[str] | None = None


class CreateAdminRequest(BaseModel):
    """Request model for creating the initial admin user."""

    username: str
    password: str
    display_name: str | None = None


class CreateAdminResponse(BaseModel):
    """Response model for admin creation."""

    success: bool
    message: str
    user_id: int | None = None
    username: str | None = None


class CreateUserRequest(BaseModel):
    """Request model for creating a new user."""

    username: str
    password: str
    user_type: str  # "customer" or "employee"
    role: str
    display_name: str | None = None
    dlp_level: str = "standard"
    can_access_all_subjects: bool = False
    subject_ids: list[str] | None = None
    # Personal data fields (for creating/updating Subject record)
    full_name: str | None = None
    document_id: str | None = None  # DNI, SSN, NIF, etc.
    tax_id: str | None = None  # CUIL/CUIT, NIF, EIN, etc.
    email: str | None = None
    phone: str | None = None


@app.get("/api/system/status", response_model=SystemStatusResponse)
def get_system_status_endpoint(
    check_llm: bool = False,
    include_errors: bool = False,
):
    """Get comprehensive system status.

    This endpoint is intentionally unauthenticated to allow the setup wizard
    to check system state before any user exists. However, it returns minimal
    information by default:

    - `check_llm=false` (default): Skip LLM health check for faster response
    - `include_errors=false` (default): Don't expose detailed error messages

    For detailed diagnostics, authenticated admins should use the admin
    dashboard or call with explicit parameters.
    """
    status = get_system_status(check_llm=check_llm, include_errors=include_errors)
    return SystemStatusResponse(**status.to_dict())


@app.post("/api/setup/create-admin", response_model=CreateAdminResponse)
def setup_create_admin(payload: CreateAdminRequest):
    """Create the initial admin user during first-run setup.

    This endpoint is ONLY available when no admin user exists (first_run=True).
    Once an admin is created, this endpoint returns 403 Forbidden.

    Security considerations:
    - This endpoint is intentionally unauthenticated (no admin exists yet)
    - It is protected by the first_run check
    - Password must meet complexity requirements
    - All actions are logged to the audit trail
    """
    try:
        result = create_initial_admin(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
        )
        return CreateAdminResponse(**result.to_dict())
    except SetupNotAllowedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except SetupValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("setup_create_admin_failed")
        raise HTTPException(status_code=500, detail="Internal error during setup")


@app.post("/api/admin/users", response_model=CreateAdminResponse)
def admin_create_user(
    payload: CreateUserRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new user (admin only).

    This endpoint allows administrators to create new users after the
    initial setup is complete. It supports creating both customer and
    employee users with various roles and permissions.

    Access control:
    - Only employees with the "admin" role can create users.
    """
    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") == "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        result = create_user(
            username=payload.username,
            password=payload.password,
            user_type=payload.user_type,
            role=payload.role,
            display_name=payload.display_name,
            dlp_level=payload.dlp_level,
            can_access_all_subjects=payload.can_access_all_subjects,
            subject_ids=payload.subject_ids,
            created_by_user_id=int(current_user.user_id),
            # Personal data fields
            full_name=payload.full_name,
            document_id=payload.document_id,
            tax_id=payload.tax_id,
            email=payload.email,
            phone=payload.phone,
        )
        return CreateAdminResponse(**result.to_dict())
    except SetupValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("admin_create_user_failed")
        raise HTTPException(status_code=500, detail="Internal error creating user")


@app.post("/api/system/init-qdrant")
def init_qdrant_collection(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Initialize the Qdrant collection (admin only).

    This endpoint creates the document collection in Qdrant if it doesn't
    exist. It's idempotent and safe to call multiple times.

    Access control:
    - Only employees with the "admin" role can call this endpoint.
    """
    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") == "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    success = ensure_qdrant_collection()
    if success:
        return {"status": "ok", "message": "Qdrant collection initialized"}
    else:
        raise HTTPException(status_code=500, detail="Failed to initialize Qdrant collection")


@app.post("/query/stream")
def query_stream(
    payload: QueryRequest,
    x_cka_api_key: str | None = Header(default=None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Streaming RAG query endpoint (Server-Sent Events).

    Returns tokens as they are generated by the LLM in real-time.
    Uses the same authentication and multi-tenant controls as /query.
    """
    # Input validation
    q = (payload.query or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail="Query must not be empty")
    if len(q) > 2000:
        raise HTTPException(status_code=413, detail="Query too long")

    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Rate limiting
    limiter_key = x_cka_api_key or payload.session_id or "global"
    if not _rate_limiter.allow(key=limiter_key):
        raise HTTPException(status_code=429, detail="rate_limited")

    # Resolve subject_id (same logic as /query)
    requested_subject = payload.subject_id
    user_type = getattr(current_user, "user_type", "customer")
    can_access_all = bool(getattr(current_user, "can_access_all_subjects", False))

    if user_type == "employee":
        if can_access_all:
            subject_id = requested_subject
        else:
            if not current_user.allowed_subject_ids:
                raise HTTPException(status_code=403, detail="No customer scope assigned")
            if requested_subject and requested_subject in current_user.allowed_subject_ids:
                subject_id = requested_subject
            else:
                subject_id = current_user.allowed_subject_ids[0]
    else:
        if not current_user.allowed_subject_ids:
            raise HTTPException(status_code=403, detail="No customer scope assigned")
        if requested_subject and requested_subject in current_user.allowed_subject_ids:
            subject_id = requested_subject
        else:
            subject_id = current_user.allowed_subject_ids[0]

    # Optionally enrich with transactional snapshot when a subject is in scope.
    customer_snapshot = None
    if subject_id:
        try:
            # Determine if this is the user's own data (for PII visibility)
            is_own_data = current_user.user_type == "customer" and subject_id in current_user.allowed_subject_ids
            viewer_role = current_user.role or current_user.user_type or "employee"

            customer_snapshot = _banking_domain_service.get_customer_snapshot(
                subject_key=subject_id,
                max_transactions=20,
                viewer_role=viewer_role,
                is_own_data=is_own_data,
            )
        except Exception:
            # Never break the main flow if the transactional DB is unavailable.
            logger.exception("banking_snapshot_failed_stream", subject_id=subject_id)

    def _generate_stream():
        """Generator for SSE events with real LLM streaming."""
        try:
            for token in _service.answer_stream(
                q,
                subject_id=subject_id,
                customer_snapshot=customer_snapshot,
                context_type=payload.context_type,
            ):
                # Send each token as SSE data event
                yield f"data: {json.dumps({'token': token})}\n\n"
            # Send completion event
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.exception("Streaming error: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        _generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.get("/chat/stream")
def chat_stream(
    q: str = "",
    x_cka_api_key: str | None = Header(default=None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Streaming chat endpoint (Server-Sent Events).

    This endpoint is gated by the same authentication and multi-tenant
    controls as /query. It is intentionally disabled by default and must be
    explicitly enabled via CKA_ENABLE_STREAMING or settings.enable_streaming.
    """

    if not (os.getenv("CKA_ENABLE_STREAMING", "").lower() in {"1", "true", "yes"} or settings.enable_streaming):
        raise HTTPException(status_code=404, detail="Streaming disabled")

    # Resolve subject_id using the same multi-tenant rules as /query.
    # For streaming we do not expose session_id or payload.subject_id, so we
    # treat this as a read under the current tenant context:
    # - Employees with can_access_all_subjects=True must still operate with
    #   an explicit subject_id chosen by the UI; here we default to the
    #   first allowed_subject_id when present.
    # - Customers are restricted to their own allowed_subject_ids.
    if not current_user.allowed_subject_ids:
        # Employees with global access but no pre-bound subjects cannot
        # stream until a tenant context is assigned.
        if getattr(current_user, "user_type", "customer") == "employee" and getattr(
            current_user, "can_access_all_subjects", False
        ):
            raise HTTPException(status_code=400, detail="Subject id is required")
        raise HTTPException(status_code=403, detail="No customer scope assigned")
    subject_id = current_user.allowed_subject_ids[0]

    # Simple rate limiting keyed by API key (same as /query)
    limiter_key = x_cka_api_key or subject_id
    if not _rate_limiter.allow(key=limiter_key):
        raise HTTPException(status_code=429, detail="rate_limited")

    answer_obj = _service.answer(q, subject_id=subject_id)
    redacted_answer = enforce_dlp(answer_obj.answer, user=current_user)

    def _iter_stream():
        # Very simple token streaming: split by space and send as SSE events.
        for token in redacted_answer.split(" "):
            yield f"data: {token}\n\n"

    return StreamingResponse(_iter_stream(), media_type="text/event-stream")


# =============================================================================
# Admin User Management Endpoints
# =============================================================================


class UserInfoResponse(BaseModel):
    """Response model for user information."""

    id: int
    username: str
    user_type: str
    role: str
    dlp_level: str
    status: str
    can_access_all_subjects: bool
    subject_ids: list[str]


class UserListResponse(BaseModel):
    """Response model for listing users."""

    users: list[UserInfoResponse]
    total: int


class UpdateUserRequest(BaseModel):
    """Request model for updating a user."""

    role: Optional[str] = None
    dlp_level: Optional[str] = None
    status: Optional[str] = None
    can_access_all_subjects: Optional[bool] = None
    new_password: Optional[str] = None


class DeleteUserResponse(BaseModel):
    """Response model for user deletion."""

    success: bool
    message: str
    user_id: int
    username: str


@app.get("/api/admin/users", response_model=UserListResponse)
def admin_list_users(
    include_inactive: bool = False,
    user_type: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all users (admin only).

    This endpoint returns a list of all users in the system.

    Query parameters:
    - include_inactive: If true, include deactivated users
    - user_type: Filter by "customer" or "employee"

    Access control:
    - Only employees with the "admin" role can list users.
    """
    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") == "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        users = list_users(
            include_inactive=include_inactive,
            user_type_filter=user_type,
        )
        return UserListResponse(
            users=[UserInfoResponse(**u.to_dict()) for u in users],
            total=len(users),
        )
    except Exception as exc:
        logger.exception("admin_list_users_failed")
        raise HTTPException(status_code=500, detail="Internal error listing users")


@app.get("/api/admin/users/{user_id}", response_model=UserInfoResponse)
def admin_get_user(
    user_id: int,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single user by ID (admin only).

    Access control:
    - Only employees with the "admin" role can view user details.
    """
    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") == "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserInfoResponse(**user.to_dict())


@app.put("/api/admin/users/{user_id}", response_model=CreateAdminResponse)
def admin_update_user(
    user_id: int,
    payload: UpdateUserRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update an existing user (admin only).

    Cannot change username or user_type. Can update:
    - role
    - dlp_level
    - status (active/inactive)
    - can_access_all_subjects
    - password (via new_password field)

    Access control:
    - Only employees with the "admin" role can update users.
    """
    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") == "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        result = update_user(
            user_id=user_id,
            role=payload.role,
            dlp_level=payload.dlp_level,
            status=payload.status,
            can_access_all_subjects=payload.can_access_all_subjects,
            new_password=payload.new_password,
            updated_by_user_id=int(current_user.user_id),
        )
        return CreateAdminResponse(**result.to_dict())
    except SetupValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("admin_update_user_failed")
        raise HTTPException(status_code=500, detail="Internal error updating user")


@app.delete("/api/admin/users/{user_id}", response_model=DeleteUserResponse)
def admin_delete_user(
    user_id: int,
    hard_delete: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete or deactivate a user (admin only).

    By default, this soft-deletes (sets status='inactive').
    Set hard_delete=true to permanently remove the user (not recommended).

    Cannot delete the last admin user.

    Access control:
    - Only employees with the "admin" role can delete users.
    """
    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") == "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        result = delete_user(
            user_id=user_id,
            deleted_by_user_id=int(current_user.user_id),
            hard_delete=hard_delete,
        )
        return DeleteUserResponse(**result.to_dict())
    except SetupValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("admin_delete_user_failed")
        raise HTTPException(status_code=500, detail="Internal error deleting user")


# =============================================================================
# TRANSACTIONAL DATA MANAGEMENT (Admin CRUD)
# =============================================================================
# These endpoints allow admins to manage service instances (products) and
# transactions (movements) for subjects. All operations require admin role
# and are fully audited.


class ServiceInstanceCreate(BaseModel):
    """Request body for creating a new service instance (product)."""

    service_type: str  # e.g. "bank_account", "credit_card", "loan"
    service_key: str  # Business identifier (IBAN, masked PAN, etc.)
    status: str = "active"
    extra_metadata: dict | None = None


class ServiceInstanceUpdate(BaseModel):
    """Request body for updating a service instance."""

    service_type: str | None = None
    service_key: str | None = None
    status: str | None = None
    extra_metadata: dict | None = None


class ServiceInstanceResponse(BaseModel):
    """Response model for a service instance."""

    id: int
    subject_id: int
    subject_key: str
    service_type: str
    service_key: str
    status: str
    opened_at: str
    closed_at: str | None
    extra_metadata: dict | None

    class Config:
        from_attributes = True


class ServiceInstanceListResponse(BaseModel):
    """Response model for listing service instances."""

    products: list[ServiceInstanceResponse]
    total: int


class TransactionCreate(BaseModel):
    """Request body for creating a new transaction."""

    transaction_type: str  # e.g. "debit", "credit", "fee"
    amount: float
    currency: str = "EUR"
    description: str | None = None
    extra_metadata: dict | None = None


class TransactionUpdate(BaseModel):
    """Request body for updating a transaction."""

    transaction_type: str | None = None
    amount: float | None = None
    currency: str | None = None
    description: str | None = None
    extra_metadata: dict | None = None


class TransactionResponse(BaseModel):
    """Response model for a transaction."""

    id: int
    service_instance_id: int
    timestamp: str
    transaction_type: str
    amount: float
    currency: str
    description: str | None
    extra_metadata: dict | None

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """Response model for listing transactions."""

    transactions: list[TransactionResponse]
    total: int
    product_info: ServiceInstanceResponse | None = None


class AdminSubjectSummary(BaseModel):
    """Subject summary for admin listing."""

    id: int
    subject_key: str
    subject_type: str
    display_name: str
    status: str
    product_count: int


class AdminSubjectListResponse(BaseModel):
    """Response model for admin subject listing."""

    subjects: list[AdminSubjectSummary]
    total: int


def _require_admin(current_user: CurrentUser) -> None:
    """Check that the current user is an admin. Raises HTTPException if not."""
    if not (getattr(current_user, "user_type", "") == "employee" and getattr(current_user, "role", "") == "admin"):
        raise HTTPException(status_code=403, detail="Forbidden: Admin role required")


def _ensure_transaction_schema() -> None:
    """Ensure the transaction tables exist in the database."""
    from ..transactions.models import Base as TxBase

    with login_db_session() as db:
        engine = db.get_bind()
        TxBase.metadata.create_all(bind=engine)


# ---------- Subjects ----------


@app.get("/api/admin/subjects", response_model=AdminSubjectListResponse)
def admin_list_subjects(
    status_filter: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all subjects with product counts (admin only).

    Optional query parameter:
    - status_filter: Filter by status (e.g. 'active', 'inactive')
    """
    _require_admin(current_user)
    _ensure_transaction_schema()

    with login_db_session() as db:
        query = db.query(Subject)
        if status_filter:
            query = query.filter(Subject.status == status_filter)

        subjects = query.order_by(Subject.id).all()
        result = []

        for subj in subjects:
            # Count products from service_instances table
            product_count = db.query(ServiceInstance).filter(ServiceInstance.subject_id == subj.id).count()
            result.append(
                AdminSubjectSummary(
                    id=subj.id,
                    subject_key=subj.subject_key,
                    subject_type=subj.subject_type,
                    display_name=subj.display_name,
                    status=subj.status,
                    product_count=product_count,
                )
            )

        return AdminSubjectListResponse(subjects=result, total=len(result))


# ---------- Service Instances (Products) ----------


@app.get(
    "/api/admin/subjects/{subject_key}/products",
    response_model=ServiceInstanceListResponse,
)
def admin_list_products(
    subject_key: str,
    status_filter: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all products/services for a subject (admin only)."""
    _require_admin(current_user)
    _ensure_transaction_schema()

    with login_db_session() as db:
        subject = db.query(Subject).filter(Subject.subject_key == subject_key).one_or_none()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        query = db.query(ServiceInstance).filter(ServiceInstance.subject_id == subject.id)
        if status_filter:
            query = query.filter(ServiceInstance.status == status_filter)

        instances = query.order_by(ServiceInstance.id).all()
        products = [
            ServiceInstanceResponse(
                id=inst.id,
                subject_id=subject.id,
                subject_key=subject.subject_key,
                service_type=inst.service_type,
                service_key=inst.service_key,
                status=inst.status,
                opened_at=inst.opened_at.isoformat() if inst.opened_at else "",
                closed_at=inst.closed_at.isoformat() if inst.closed_at else None,
                extra_metadata=dict(inst.extra_metadata) if inst.extra_metadata else None,
            )
            for inst in instances
        ]

        return ServiceInstanceListResponse(products=products, total=len(products))


@app.post(
    "/api/admin/subjects/{subject_key}/products",
    response_model=ServiceInstanceResponse,
    status_code=201,
)
def admin_create_product(
    subject_key: str,
    data: ServiceInstanceCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new product/service for a subject (admin only).

    Required fields:
    - service_type: Type of service (e.g. 'bank_account', 'credit_card', 'loan')
    - service_key: Business identifier (must be unique per subject)
    """
    _require_admin(current_user)
    _ensure_transaction_schema()

    # Input validation
    if not data.service_type or not data.service_type.strip():
        raise HTTPException(status_code=400, detail="service_type is required")
    if not data.service_key or not data.service_key.strip():
        raise HTTPException(status_code=400, detail="service_key is required")

    # Sanitize inputs (basic XSS prevention)
    service_type = data.service_type.strip()[:64]
    service_key = data.service_key.strip()[:128]
    status = (data.status or "active").strip()[:32]

    with login_db_session() as db:
        subject = db.query(Subject).filter(Subject.subject_key == subject_key).one_or_none()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check for duplicate service_key within subject
        existing = (
            db.query(ServiceInstance)
            .filter(
                ServiceInstance.subject_id == subject.id,
                ServiceInstance.service_key == service_key,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Product with this service_key already exists")

        instance = ServiceInstance(
            subject_id=subject.id,
            service_type=service_type,
            service_key=service_key,
            status=status,
            extra_metadata=data.extra_metadata,
        )
        db.add(instance)
        db.flush()

        # Audit
        _audit(
            login_db_session,
            operation="admin_create_product",
            outcome="success",
            user_id=str(current_user.user_id),
            subject_key=subject_key,
            details={
                "product_id": instance.id,
                "service_type": service_type,
                "service_key": service_key,
            },
        )

        logger.info(
            "admin_product_created",
            product_id=instance.id,
            subject_key=subject_key,
            service_type=service_type,
            created_by=current_user.user_id,
        )

        return ServiceInstanceResponse(
            id=instance.id,
            subject_id=subject.id,
            subject_key=subject.subject_key,
            service_type=instance.service_type,
            service_key=instance.service_key,
            status=instance.status,
            opened_at=instance.opened_at.isoformat() if instance.opened_at else "",
            closed_at=instance.closed_at.isoformat() if instance.closed_at else None,
            extra_metadata=dict(instance.extra_metadata) if instance.extra_metadata else None,
        )


@app.put("/api/admin/products/{product_id}", response_model=ServiceInstanceResponse)
def admin_update_product(
    product_id: int,
    data: ServiceInstanceUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a product/service (admin only)."""
    _require_admin(current_user)

    with login_db_session() as db:
        instance = db.query(ServiceInstance).filter(ServiceInstance.id == product_id).one_or_none()
        if not instance:
            raise HTTPException(status_code=404, detail="Product not found")

        subject = db.query(Subject).filter(Subject.id == instance.subject_id).one_or_none()
        subject_key = subject.subject_key if subject else "unknown"

        changes = []
        if data.service_type is not None:
            instance.service_type = data.service_type.strip()[:64]
            changes.append("service_type")
        if data.service_key is not None:
            instance.service_key = data.service_key.strip()[:128]
            changes.append("service_key")
        if data.status is not None:
            instance.status = data.status.strip()[:32]
            changes.append("status")
        if data.extra_metadata is not None:
            instance.extra_metadata = data.extra_metadata
            changes.append("extra_metadata")

        db.flush()

        _audit(
            login_db_session,
            operation="admin_update_product",
            outcome="success",
            user_id=str(current_user.user_id),
            subject_key=subject_key,
            details={"product_id": product_id, "changes": changes},
        )

        logger.info(
            "admin_product_updated",
            product_id=product_id,
            changes=changes,
            updated_by=current_user.user_id,
        )

        return ServiceInstanceResponse(
            id=instance.id,
            subject_id=instance.subject_id,
            subject_key=subject_key,
            service_type=instance.service_type,
            service_key=instance.service_key,
            status=instance.status,
            opened_at=instance.opened_at.isoformat() if instance.opened_at else "",
            closed_at=instance.closed_at.isoformat() if instance.closed_at else None,
            extra_metadata=dict(instance.extra_metadata) if instance.extra_metadata else None,
        )


@app.delete("/api/admin/products/{product_id}")
def admin_delete_product(
    product_id: int,
    hard_delete: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete or deactivate a product (admin only).

    By default, soft-deletes (sets status='closed'). Use hard_delete=true to
    permanently remove (cascades to transactions).
    """
    _require_admin(current_user)

    with login_db_session() as db:
        instance = db.query(ServiceInstance).filter(ServiceInstance.id == product_id).one_or_none()
        if not instance:
            raise HTTPException(status_code=404, detail="Product not found")

        subject = db.query(Subject).filter(Subject.id == instance.subject_id).one_or_none()
        subject_key = subject.subject_key if subject else "unknown"

        if hard_delete:
            # Delete all associated transactions first (manual cascade for safety)
            db.query(ServiceTransaction).filter(ServiceTransaction.service_instance_id == product_id).delete(
                synchronize_session=False
            )
            db.delete(instance)
            action = "hard_deleted"
        else:
            from datetime import datetime, timezone

            instance.status = "closed"
            instance.closed_at = datetime.now(timezone.utc)
            action = "soft_deleted"

        db.flush()

        _audit(
            login_db_session,
            operation="admin_delete_product",
            outcome="success",
            user_id=str(current_user.user_id),
            subject_key=subject_key,
            details={
                "product_id": product_id,
                "action": action,
                "hard_delete": hard_delete,
            },
        )

        logger.info(
            "admin_product_deleted",
            product_id=product_id,
            action=action,
            deleted_by=current_user.user_id,
        )

        return {
            "success": True,
            "message": f"Product {action}",
            "product_id": product_id,
        }


# ---------- Transactions (Movements) ----------


@app.get(
    "/api/admin/products/{product_id}/transactions",
    response_model=TransactionListResponse,
)
def admin_list_transactions(
    product_id: int,
    limit: int = 50,
    offset: int = 0,
    tx_type: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List transactions for a product (admin only).

    Supports pagination via limit/offset and filtering by transaction type.
    """
    _require_admin(current_user)
    _ensure_transaction_schema()

    # Validate pagination params
    limit = min(max(1, limit), 500)  # Between 1 and 500
    offset = max(0, offset)

    with login_db_session() as db:
        instance = db.query(ServiceInstance).filter(ServiceInstance.id == product_id).one_or_none()
        if not instance:
            raise HTTPException(status_code=404, detail="Product not found")

        subject = db.query(Subject).filter(Subject.id == instance.subject_id).one_or_none()
        subject_key = subject.subject_key if subject else "unknown"

        query = db.query(ServiceTransaction).filter(ServiceTransaction.service_instance_id == product_id)
        if tx_type:
            query = query.filter(ServiceTransaction.transaction_type == tx_type)

        total = query.count()
        txs = query.order_by(ServiceTransaction.timestamp.desc()).offset(offset).limit(limit).all()

        transactions = [
            TransactionResponse(
                id=tx.id,
                service_instance_id=tx.service_instance_id,
                timestamp=tx.timestamp.isoformat() if tx.timestamp else "",
                transaction_type=tx.transaction_type,
                amount=tx.amount,
                currency=tx.currency,
                description=tx.description,
                extra_metadata=dict(tx.extra_metadata) if tx.extra_metadata else None,
            )
            for tx in txs
        ]

        product_info = ServiceInstanceResponse(
            id=instance.id,
            subject_id=instance.subject_id,
            subject_key=subject_key,
            service_type=instance.service_type,
            service_key=instance.service_key,
            status=instance.status,
            opened_at=instance.opened_at.isoformat() if instance.opened_at else "",
            closed_at=instance.closed_at.isoformat() if instance.closed_at else None,
            extra_metadata=dict(instance.extra_metadata) if instance.extra_metadata else None,
        )

        return TransactionListResponse(transactions=transactions, total=total, product_info=product_info)


@app.post(
    "/api/admin/products/{product_id}/transactions",
    response_model=TransactionResponse,
    status_code=201,
)
def admin_create_transaction(
    product_id: int,
    data: TransactionCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new transaction for a product (admin only).

    Required fields:
    - transaction_type: Type of transaction (e.g. 'debit', 'credit', 'fee')
    - amount: Transaction amount (positive for credits, negative for debits)
    """
    _require_admin(current_user)
    _ensure_transaction_schema()

    # Input validation
    if not data.transaction_type or not data.transaction_type.strip():
        raise HTTPException(status_code=400, detail="transaction_type is required")

    # Sanitize inputs
    tx_type = data.transaction_type.strip()[:64]
    currency = (data.currency or "EUR").strip()[:8]
    description = data.description[:256] if data.description else None

    with login_db_session() as db:
        instance = db.query(ServiceInstance).filter(ServiceInstance.id == product_id).one_or_none()
        if not instance:
            raise HTTPException(status_code=404, detail="Product not found")

        subject = db.query(Subject).filter(Subject.id == instance.subject_id).one_or_none()
        subject_key = subject.subject_key if subject else "unknown"

        tx = ServiceTransaction(
            service_instance_id=product_id,
            transaction_type=tx_type,
            amount=data.amount,
            currency=currency,
            description=description,
            extra_metadata=data.extra_metadata,
        )
        db.add(tx)
        db.flush()

        _audit(
            login_db_session,
            operation="admin_create_transaction",
            outcome="success",
            user_id=str(current_user.user_id),
            subject_key=subject_key,
            details={
                "transaction_id": tx.id,
                "product_id": product_id,
                "type": tx_type,
                "amount": data.amount,
                "currency": currency,
            },
        )

        logger.info(
            "admin_transaction_created",
            transaction_id=tx.id,
            product_id=product_id,
            tx_type=tx_type,
            amount=data.amount,
            created_by=current_user.user_id,
        )

        return TransactionResponse(
            id=tx.id,
            service_instance_id=tx.service_instance_id,
            timestamp=tx.timestamp.isoformat() if tx.timestamp else "",
            transaction_type=tx.transaction_type,
            amount=tx.amount,
            currency=tx.currency,
            description=tx.description,
            extra_metadata=dict(tx.extra_metadata) if tx.extra_metadata else None,
        )


@app.put("/api/admin/transactions/{transaction_id}", response_model=TransactionResponse)
def admin_update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a transaction (admin only)."""
    _require_admin(current_user)

    with login_db_session() as db:
        tx = db.query(ServiceTransaction).filter(ServiceTransaction.id == transaction_id).one_or_none()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")

        instance = db.query(ServiceInstance).filter(ServiceInstance.id == tx.service_instance_id).one_or_none()
        subject = None
        if instance:
            subject = db.query(Subject).filter(Subject.id == instance.subject_id).one_or_none()
        subject_key = subject.subject_key if subject else "unknown"

        changes = []
        if data.transaction_type is not None:
            tx.transaction_type = data.transaction_type.strip()[:64]
            changes.append("transaction_type")
        if data.amount is not None:
            tx.amount = data.amount
            changes.append("amount")
        if data.currency is not None:
            tx.currency = data.currency.strip()[:8]
            changes.append("currency")
        if data.description is not None:
            tx.description = data.description[:256] if data.description else None
            changes.append("description")
        if data.extra_metadata is not None:
            tx.extra_metadata = data.extra_metadata
            changes.append("extra_metadata")

        db.flush()

        _audit(
            login_db_session,
            operation="admin_update_transaction",
            outcome="success",
            user_id=str(current_user.user_id),
            subject_key=subject_key,
            details={"transaction_id": transaction_id, "changes": changes},
        )

        logger.info(
            "admin_transaction_updated",
            transaction_id=transaction_id,
            changes=changes,
            updated_by=current_user.user_id,
        )

        return TransactionResponse(
            id=tx.id,
            service_instance_id=tx.service_instance_id,
            timestamp=tx.timestamp.isoformat() if tx.timestamp else "",
            transaction_type=tx.transaction_type,
            amount=tx.amount,
            currency=tx.currency,
            description=tx.description,
            extra_metadata=dict(tx.extra_metadata) if tx.extra_metadata else None,
        )


@app.delete("/api/admin/transactions/{transaction_id}")
def admin_delete_transaction(
    transaction_id: int,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a transaction (admin only). This is a hard delete."""
    _require_admin(current_user)

    with login_db_session() as db:
        tx = db.query(ServiceTransaction).filter(ServiceTransaction.id == transaction_id).one_or_none()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")

        product_id = tx.service_instance_id
        instance = db.query(ServiceInstance).filter(ServiceInstance.id == product_id).one_or_none()
        subject = None
        if instance:
            subject = db.query(Subject).filter(Subject.id == instance.subject_id).one_or_none()
        subject_key = subject.subject_key if subject else "unknown"

        db.delete(tx)
        db.flush()

        _audit(
            login_db_session,
            operation="admin_delete_transaction",
            outcome="success",
            user_id=str(current_user.user_id),
            subject_key=subject_key,
            details={"transaction_id": transaction_id, "product_id": product_id},
        )

        logger.info(
            "admin_transaction_deleted",
            transaction_id=transaction_id,
            product_id=product_id,
            deleted_by=current_user.user_id,
        )

        return {
            "success": True,
            "message": "Transaction deleted",
            "transaction_id": transaction_id,
        }


# =============================================================================
# SUBJECT DATA ADMINISTRATION (Auditable CRUD)
# =============================================================================
# These endpoints allow admins to view and modify subject data with full
# audit trail. Every modification requires a reason and generates an
# immutable audit record.


class SubjectDataResponse(BaseModel):
    """Response model for subject data."""

    subject_key: str
    subject_type: str | None
    display_name: str | None
    status: str | None
    full_name: str | None
    document_id: str | None
    tax_id: str | None
    email: str | None
    phone: str | None
    created_at: str | None
    updated_at: str | None


class SubjectUpdateRequest(BaseModel):
    """Request model for updating subject data.

    All fields are optional. Only provided fields will be updated.
    A reason is REQUIRED to document the change.
    """

    display_name: str | None = None
    full_name: str | None = None
    document_id: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    subject_type: str | None = None
    reason: str  # Required - justification for the change


class SubjectUpdateResponse(BaseModel):
    """Response model for subject data update."""

    success: bool
    message: str
    subject_key: str | None
    changes_count: int
    audit_id: int | None


class SubjectHistoryResponse(BaseModel):
    """Response model for subject modification history."""

    audit_id: int
    timestamp: str | None
    operator_user_id: str | None
    operator_username: str | None
    outcome: str
    details: dict | None


@app.get("/api/admin/subjects/{subject_key}/data", response_model=SubjectDataResponse)
def admin_get_subject_data(
    subject_key: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get subject data for editing (admin only).

    Returns all editable fields for a subject, including personal data.
    This is used by the admin UI to populate the edit form.
    """
    _require_admin(current_user)

    from cortex_ka.system.data_admin import get_subject_for_edit

    data = get_subject_for_edit(subject_key)
    if not data:
        raise HTTPException(status_code=404, detail="Subject not found")

    return SubjectDataResponse(**data)


@app.put("/api/admin/subjects/{subject_key}/data", response_model=SubjectUpdateResponse)
def admin_update_subject_data(
    subject_key: str,
    payload: SubjectUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update subject data with full audit trail (admin only).

    This endpoint allows modifying subject personal data with comprehensive
    auditing. Every change is recorded with:
    - Timestamp (UTC)
    - Operator identity
    - Before/After values (PII fields are hashed)
    - Reason/justification

    Required:
    - reason: A meaningful justification (min 10 characters)

    Optional (only provided fields are updated):
    - display_name, full_name, document_id, tax_id, email, phone, status, subject_type
    """
    _require_admin(current_user)

    from cortex_ka.system.data_admin import ValidationError as DataValidationError
    from cortex_ka.system.data_admin import (
        update_subject_data,
    )

    # Build updates dict from payload (exclude None and 'reason')
    updates = {}
    for field in [
        "display_name",
        "full_name",
        "document_id",
        "tax_id",
        "email",
        "phone",
        "status",
        "subject_type",
    ]:
        value = getattr(payload, field, None)
        if value is not None:
            updates[field] = value

    # Get client IP for audit
    client_ip = request.client.host if request.client else None

    try:
        result = update_subject_data(
            subject_key=subject_key,
            updates=updates,
            reason=payload.reason,
            operator_user_id=int(current_user.user_id),
            operator_username=getattr(current_user, "username", None),
            operator_ip=client_ip,
        )
        return SubjectUpdateResponse(**result.to_dict())
    except DataValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("admin_update_subject_data_failed")
        raise HTTPException(status_code=500, detail="Internal error updating subject")


@app.get(
    "/api/admin/subjects/{subject_key}/history",
    response_model=list[SubjectHistoryResponse],
)
def admin_get_subject_history(
    subject_key: str,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get modification history for a subject (admin only).

    Returns all audit records related to data modifications for this subject,
    ordered by most recent first.
    """
    _require_admin(current_user)

    from cortex_ka.system.data_admin import list_subject_modification_history

    history = list_subject_modification_history(subject_key, limit=limit)
    return [SubjectHistoryResponse(**h) for h in history]


# =============================================================================
# DOCUMENT UPLOAD ENDPOINT
# =============================================================================
# Endpoint for uploading public documentation files


@app.post("/api/admin/upload-public-document")
async def admin_upload_public_document(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Upload a public documentation file (admin only).

    This endpoint accepts a file upload and stores it in the public
    documentation folder. The file will be processed and ingested into
    Qdrant for RAG queries.

    Supported formats: PDF, TXT, MD
    Max file size: 50MB

    Form fields:
    - file: The document file to upload
    - category: Document category (public_docs or educational)

    The upload is fully audited with:
    - Filename and size
    - SHA-256 hash of content
    - Operator identity
    - Timestamp
    """
    _require_admin(current_user)

    import hashlib
    import os
    from pathlib import Path

    from cortex_ka.system.data_admin import record_document_upload

    # Parse multipart form data
    form = await request.form()
    file = form.get("file")
    category = form.get("category", "public_docs")

    # Validate category
    valid_categories = {"public_docs", "educational"}
    if category not in valid_categories:
        category = "public_docs"

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Get filename and validate extension
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    allowed_extensions = {".pdf", ".txt", ".md"}
    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    # Read file content
    content = await file.read()

    # Check file size (50MB max - increased for large documents)
    max_size = 50 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_size // (1024 * 1024)}MB",
        )

    # Calculate hash
    file_hash = hashlib.sha256(content).hexdigest()

    # Determine destination path based on category
    import os

    base_data_dir = Path(os.environ.get("CKA_DATA_DIR", "/app/data"))
    if category == "educational":
        docs_dir = base_data_dir / "documentacion" / "educativa"
    else:
        docs_dir = base_data_dir / "documentacion" / "publica"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename (prevent path traversal)
    safe_filename = Path(filename).name
    # Add hash prefix to prevent overwrites
    unique_filename = f"{file_hash[:8]}_{safe_filename}"
    destination = docs_dir / unique_filename

    # Write file
    destination.write_bytes(content)

    # Get client IP
    client_ip = request.client.host if request.client else None

    # Record in audit log
    audit_id = record_document_upload(
        filename=filename,
        file_size=len(content),
        file_hash=file_hash,
        destination_path=str(destination),
        operator_user_id=int(current_user.user_id),
        operator_username=getattr(current_user, "username", None),
        operator_ip=client_ip,
    )

    # Trigger ingestion of ONLY this document (not all documents)
    try:
        # Extract text content based on file type
        if ext == ".pdf":
            # Use pypdf for PDF text extraction (already a dependency)
            import io

            from pypdf import PdfReader

            # Extract text from PDF
            pdf_stream = io.BytesIO(content)
            reader = PdfReader(pdf_stream)
            text_content = ""
            for page in reader.pages:
                text_content += page.extract_text() or ""
        else:
            # TXT and MD files - decode directly
            text_content = content.decode("utf-8", errors="replace")

        # Ingest only this document with its category
        result = ingest_single_document(
            content=text_content,
            filename=safe_filename,
            category=category,
            doc_id=f"{file_hash[:8]}_{Path(safe_filename).stem}",
        )
        ingested_count = result.total_points
        ingestion_status = "success" if result.verification_passed else "pending"

        logger.info(
            "single_document_upload_complete",
            filename=unique_filename,
            category=category,
            points_created=ingested_count,
        )
    except Exception as exc:
        logger.exception("document_ingestion_failed_after_upload")
        ingested_count = 0
        ingestion_status = "pending"

    return {
        "success": True,
        "message": "Document uploaded and processed",
        "filename": unique_filename,
        "file_size": len(content),
        "file_hash": file_hash,
        "audit_id": audit_id,
        "ingestion_status": ingestion_status,
        "documents_ingested": ingested_count,
        "category": category,
    }
