"""Background file imports and SaaS connections (RushDB Cloud).

Both write through import runs: an import run is created for every file
import and every connection sync, and continues on the server without the
client. Poll it with ``db.imports.get(id)`` or ``db.imports.wait(id)``.

The types mirror the JSON the API sends and receives, so their keys are
camelCase.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict, Union

# ── import runs ──────────────────────────────────────────────────────────────

ImportRunKind = Literal["file", "sync"]
ImportRunTrigger = Literal["manual", "schedule", "webhook", "api", "retry", "once"]
ImportRunStatus = Literal[
    "draft",
    "queued",
    "running",
    "paused_billing",
    "completed",
    "partial",
    "failed",
    "cancelled",
]

FINISHED_IMPORT_RUN_STATUSES: Tuple[str, ...] = (
    "completed",
    "partial",
    "failed",
    "cancelled",
)
"""Statuses after which a run no longer changes (until it is retried)."""


class _ImportRunPartRequired(TypedDict):
    status: Literal["pending", "running", "done", "failed", "skipped"]
    records: int


class ImportRunPart(_ImportRunPartRequired, total=False):
    """Progress of one file or one stream of a run."""

    label: str
    title: str
    deleted: int
    links: int
    bytes: int
    totalBytes: int
    errors: int
    error: str


class ImportRunError(TypedDict, total=False):
    part: str
    row: int
    externalId: str
    message: str


class ImportRunSummary(TypedDict, total=False):
    """What a run found after it finished."""

    labels: List[str]
    suggestions: int
    awaitingEmbeddings: int
    durationMs: int


# ── personal data ────────────────────────────────────────────────────────────

PiiKind = Literal[
    "email",
    "phone",
    "name",
    "address",
    "birthdate",
    "national_id",
    "tax_id",
    "payment_card",
    "bank_account",
    "ip_address",
    "credentials",
    "compensation",
    "health",
    "location",
    "free_text",
]


class PiiFinding(TypedDict):
    """Why a field or column looks like personal data."""

    kind: PiiKind
    source: Literal["name", "value"]
    confidence: float
    reason: str


# ── file imports ─────────────────────────────────────────────────────────────

ImportColumnType = Literal["string", "number", "boolean", "datetime"]


class ImportFileMapping(TypedDict, total=False):
    """How one file maps to the graph."""

    keyColumn: str
    """Column whose value identifies a row across imports: re-importing upserts."""
    skip: List[str]
    hash: List[str]
    """Columns kept as a keyed hash: joinable across sources, not readable."""
    rename: Dict[str, str]
    types: Dict[str, ImportColumnType]
    delimiter: str
    """CSV only."""


class ImportFileLink(TypedDict):
    """A link between two files of one import: rows whose ``sourceColumn``
    equals the target's ``targetColumn``."""

    sourceFileId: str
    sourceColumn: str
    targetFileId: str
    targetColumn: str
    type: str


class ImportFile(TypedDict):
    id: str
    name: str
    format: str
    compression: Optional[str]
    size: int
    status: str
    label: str
    mapping: Optional[ImportFileMapping]
    rowsDone: int
    bytesDone: int
    errorCount: int
    error: Optional[str]


class S3PartUrl(TypedDict):
    partNumber: int
    url: str


class S3MultipartUpload(TypedDict):
    """Parts go to presigned PUT URLs, without the API auth header."""

    mode: Literal["s3-multipart"]
    partSize: int
    parts: List[S3PartUrl]
    expiresAt: str


class DirectUpload(TypedDict):
    """Through the API: ``PUT`` the raw bytes to ``path`` with the usual auth header."""

    mode: Literal["direct"]
    method: Literal["PUT"]
    path: str


ImportUploadInstructions = Union[S3MultipartUpload, DirectUpload]


class ImportFileUpload(ImportFile):
    """A file with its upload instructions, as ``create``/``add_files`` return it."""

    upload: ImportUploadInstructions


class _ImportRunRequired(TypedDict):
    id: str
    kind: ImportRunKind
    trigger: ImportRunTrigger
    status: ImportRunStatus
    name: Optional[str]
    connectionId: Optional[str]
    recordsWritten: int
    recordsDeleted: int
    linksCreated: int
    errorCount: int
    progress: Dict[str, ImportRunPart]
    """Per file (file imports) or per stream (syncs)."""
    errorSample: List[ImportRunError]
    summary: Optional[ImportRunSummary]
    error: Optional[str]
    startedBy: Optional[Dict[str, Any]]
    startedAt: Optional[str]
    finishedAt: Optional[str]
    createdAt: str
    updatedAt: str


class ImportRun(_ImportRunRequired, total=False):
    """One import run (a file import or a connection sync) with its progress."""

    files: List[ImportFile]
    options: Optional[Dict[str, Any]]


class CreatedImport(_ImportRunRequired):
    """A draft import whose files carry their upload instructions."""

    files: List[ImportFileUpload]


class _ImportFileInputRequired(TypedDict):
    name: str
    size: int


class ImportFileInput(_ImportFileInputRequired, total=False):
    """A file announced to ``imports.create``: its name (the extension picks
    the parser) and exact size in bytes."""

    label: str


class _ImportFileSettingsRequired(TypedDict):
    id: str


class ImportFileSettings(_ImportFileSettingsRequired, total=False):
    """Settings of one uploaded file for ``preview`` and ``start``."""

    label: str
    mapping: ImportFileMapping


class ImportColumnProfile(TypedDict, total=False):
    name: str
    type: ImportColumnType
    samples: List[Any]
    nulls: int
    distinct: int
    unique: bool
    pii: PiiFinding
    """Looks like personal data; its samples are masked then."""
    suggestion: Literal["include", "skip", "hash"]


class ImportFilePreview(TypedDict, total=False):
    fileId: str
    name: str
    label: str
    rows: int
    columns: List[ImportColumnProfile]
    suggestedKey: str
    errors: List[str]


class ImportLinkSuggestion(ImportFileLink):
    confidence: float
    reason: str


class ImportPreview(TypedDict):
    files: List[ImportFilePreview]
    links: List[ImportLinkSuggestion]


class ImportUploadProgress(TypedDict):
    fileId: str
    loaded: int
    """Bytes sent so far for this file."""
    total: int


class ImportFilesLink(TypedDict):
    """A link for ``imports.import_files``, naming files by position or name."""

    source: Union[int, str]
    """The source file, by position in the list or by name."""
    sourceColumn: str
    target: Union[int, str]
    targetColumn: str
    type: str


class ImportFilesProgress(TypedDict, total=False):
    """``{"phase": "upload", "fileId", "loaded", "total"}`` while uploading,
    then ``{"phase": "run", "run": ImportRun}``."""

    phase: Literal["upload", "run"]
    fileId: str
    loaded: int
    total: int
    run: ImportRun


# ── connections ──────────────────────────────────────────────────────────────

ConnectionMode = Literal[
    "once", "scheduled", "manual", "webhook_trigger", "webhook_push", "agent"
]
ConnectionStatus = Literal["draft", "ready", "paused", "needs_reauth"]
ConnectionDeleteMode = Literal["soft", "hard", "ignore"]


class FieldPolicy(TypedDict, total=False):
    """Which fields of a stream reach the graph. ``auto`` keeps every field
    except what is excluded or hashed; ``allowlist`` keeps only reviewed
    fields (``include``, ``hash``), and new fields wait in ``unreviewed``."""

    mode: Literal["auto", "allowlist"]
    include: List[str]
    exclude: List[str]
    hash: List[str]
    reviewedAt: str
    reviewedBy: str


class FieldProfile(TypedDict, total=False):
    """One field of a stream as sampled for the field review."""

    name: str
    type: Literal["string", "number", "boolean", "datetime", "array", "null"]
    coverage: float
    pii: PiiFinding
    example: str
    """A masked example (never a raw value of a field that looks personal)."""
    suggestion: Literal["include", "exclude", "hash"]


class ConnectionFieldsReview(TypedDict):
    """``connections.fields``: the field review of one stream."""

    stream: str
    label: str
    sampled: int
    fields: List[FieldProfile]
    policy: FieldPolicy
    unreviewed: List[str]


class FieldChoice(TypedDict):
    """A reviewer's choice for one field, for ``connections.review_fields``."""

    name: str
    action: Literal["include", "exclude", "hash"]


class PushTemplate(TypedDict, total=False):
    """How Zapier, Make or n8n push records into a webhook (push) connection."""

    id: str
    name: str
    description: str
    docsUrl: str
    steps: List[str]
    """Steps in order; ``{{pushUrl}}`` stands for the connection's push URL."""
    samplePayload: Dict[str, Any]
    logo: str


class ConnectionStream(TypedDict, total=False):
    stream: str
    enabled: bool
    label: str
    deleteMode: ConnectionDeleteMode
    policy: FieldPolicy
    reviewed: bool
    unreviewed: List[str]
    records: int
    lastSyncedAt: Optional[str]
    cursor: Union[str, int, None]
    description: str
    optional: bool


class Connection(TypedDict, total=False):
    id: str
    name: str
    connectorId: str
    specId: Optional[str]
    connectorName: str
    status: ConnectionStatus
    mode: ConnectionMode
    scheduleMinutes: Optional[int]
    nextRunAt: Optional[str]
    config: Dict[str, Any]
    authType: Optional[str]
    account: Optional[str]
    hasCredentials: bool
    hasWebhookSecret: bool
    webhookUrl: Optional[str]
    customWebhookUrl: Optional[str]
    hasCustomWebhookToken: bool
    webhookSetup: Optional[str]
    lastRunAt: Optional[str]
    lastSuccessAt: Optional[str]
    lastWebhookAt: Optional[str]
    lastError: Optional[str]
    activeRunId: Optional[str]
    agent: Optional[Dict[str, Any]]
    """Agent connections: what the agent last reported."""
    logo: str
    streams: List[ConnectionStream]
    createdAt: str
    updatedAt: str


class CatalogConnector(TypedDict, total=False):
    id: str
    name: str
    category: str
    description: str
    docsUrl: str
    auth: List[str]
    streams: List[Dict[str, Any]]
    config: Dict[str, Dict[str, Any]]
    webhooks: bool
    incremental: bool
    beta: bool
    oauthAvailable: bool
    custom: Dict[str, Any]
    logo: str


class ConnectionStreamSettings(TypedDict, total=False):
    stream: str
    enabled: bool
    label: str
    deleteMode: ConnectionDeleteMode
    policy: FieldPolicy


class UpdateConnectionParams(TypedDict, total=False):
    """Fields of a connection that can be set on create and update."""

    name: str
    config: Dict[str, Union[str, List[str]]]
    auth: Dict[str, str]
    """``{"type": "bearer", "token"}``, ``{"type": "apiKey", "apiKey"}``,
    ``{"type": "basic", "username", "password"}`` or ``{"type": "none"}``."""
    oauthApp: Dict[str, str]
    webhookSecret: str
    mode: ConnectionMode
    scheduleMinutes: int
    """5 minutes to 7 days."""
    streams: List[ConnectionStreamSettings]
    push: Dict[str, str]
    """Push connections: ``{"label", "keyField"}``."""
    agent: Dict[str, int]
    """Agent connections: ``{"intervalMinutes"}`` (1–1440)."""
    specId: str


class CreateConnectionParams(UpdateConnectionParams, total=False):
    connectorId: str
    """A built-in connector id (see ``catalog()``), ``custom`` (with
    ``specId``), ``webhook`` (push) or ``agent`` (on-prem agent). Required."""


class _CreatedConnectionRequired(TypedDict):
    connection: Connection


class CreatedConnection(_CreatedConnectionRequired, total=False):
    """Tokens are returned once: ``webhookToken`` for push and trigger
    connections, ``agentToken`` (for ``rushdb-agent``) for agent connections."""

    webhookToken: str
    agentToken: str


class ConnectionTestResult(TypedDict, total=False):
    ok: bool
    account: str
    error: str


class ConnectionPreview(TypedDict):
    stream: str
    label: str
    records: List[Dict[str, Any]]


class _DeletedConnectionRequired(TypedDict):
    deleted: bool


class DeletedConnection(_DeletedConnectionRequired, total=False):
    recordsDeleted: int


class ConnectionWebhookToken(TypedDict):
    """The new token with its URL; shown once."""

    token: str
    url: str
