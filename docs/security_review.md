# Security Review (T113) — OWASP API Security Top 10

Review pass over the initial release. Every item notes whether it is
covered, where, or that it is a documented forward concern.

| OWASP API Top 10 (2023) item | State | Where / evidence |
|---|---|---|
| **API1 Broken Object-Level Authorization** | ✅ Covered | Every repository query is owner-scoped (`app/adapters/persistence/mongodb/repositories/base.py` + per-repo owner filters); cross-user thread access → 404/403 (`AssistantService`, `app/api/v1/dependencies/auth.py::owner_of`). Tests: `tests/api/test_assistant.py::test_cross_user_access_rejected`, repository owner-scoping integration tests. |
| **API2 Broken Authentication** | ✅ Covered (mechanism documented as deferred) | HMAC-SHA256 signed tokens (`app/adapters/external/auth/token_authenticator.py`), TTL + logout revocation via `users.session_valid_after`; password hashes PBKDF2 (100k, salted); 401 for missing/invalid tokens (`tests/api/test_users.py::test_unauthenticated_access_is_rejected`). The final mechanism requires the deferred approval (plan.md open decision 7). |
| **API3 Broken Object-Property-Level Authorization** | ✅ Covered | Response serializers strip `password_hash`/`session_valid_after` (`app/api/v1/endpoints/auth.py::user_response`); request models use `extra="forbid"` (no mass-assignment); profile updates enumerate an explicit allow-list (`app/services/user_service.py::update_me`). |
| **API4 Unrestricted Resource Consumption** | ⚠️ Partially: forward concern | Rate limiting is documented as deferred (contract § Cross-cutting). Mitigations in place: bounded corrective loop (A-10), bounded VCR, request-body pydantic limits, bounded history/list limits in repositories (`limit=` caps). |
| **API5 Broken Function-Level Authorization** | ✅ Covered | Feature gates consult the store per request (`FeatureAvailabilityService.ensure_enabled`); unapproved material is never delivered (FR-042); approval gate never bypassed (`DailyMaterialService` only persists an `approved` evaluation; `corrective_loop` returns approved output only). |
| **API6 Unrestricted Access to Sensitive Business Flows** | ✅ Covered | The sensitive flow (content generation) is bound: per-user RAG isolation, bounded loop, audit rows for every attempt (FR-086). |
| **API7 Server Side Request Forgery** | ✅ Covered | No server-side fetch of user-supplied URLs: platform URLs are stored as provided (A-5) and used only inside email bodies; the only outbound endpoints are the configured LocalStack/secrets providers (`SECRETS_ENDPOINT_URL` from configuration, never from request input). |
| **API8 Security Misconfiguration** | ✅ Covered | Missing mandatory configuration refuses to start (`Settings.validate_mandatory`, `MongoClientWrapper`); no real credentials committed (`git grep 'AKIA[0-9A-Z]{16}'` clean; dummy- prefixed values only); test deps never ship in the runtime image (`scripts/image_content_check.sh`). |
| **API9 Improper Inventory Management** | ✅ Covered | API versioned under `/api/v1`; contract is the single source (`contracts/README.md`); undocumented endpoints do not exist. |
| **API10 Unsafe Consumption of APIs** | ✅ Covered | Emulated-SES/secret responses are validated before use (`LocalStackSecretProvider` raises on non-200 / missing value); VCR keeps HTTP out of the suite; failures contained (constitution X). |

## Additional reviews

- **Injection**: all persistence flows go through pydantic-validated entities and
  parameterized PyMongo documents (no string-built queries). The one regex use
  (`search_approved_by_user`) has a user-supplied pattern — a future hardening
  should escape regex metacharacters; documented here as a known improvement
  item (not a route currently exposed by any endpoint).
- **Logs**: `SecretRedactingFilter` masks credential-looking values; no PII or
  raw learning content beyond bounded excerpts in audit payloads.
- **Cookies/session**: stateless bearer tokens; `HttpOnly` cookies N/A this release.

## Known deferred items (documented, require approval)

1. Rate limiting (API4) — operations plan.
2. Final authentication mechanism (API2) — approval per research.md § 7.
3. Regex escaping in best-effort material search — small hardening task.