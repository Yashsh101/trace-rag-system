# Security Policy

## Current Controls

- All non-health endpoints require `X-API-Key`.
- Admin and user keys are configured via environment variables.
- Document ACLs are enforced before retrieval and again before context assembly.
- Retrieved text is treated as untrusted source data.
- Answers without strong cited support return no-answer.
- Uploads have size, extension, content-type, and PDF magic-byte validation.
- Structured logs include trace IDs for auditability.
- Duplicate document dedupe is scoped by owner to prevent cross-user ACL inheritance.
- API rate limiting is Redis-backed in production and memory-backed for local development.

## Reporting Issues

Do not include secrets, private documents, or production data in reports. Include:

- endpoint
- trace ID
- expected behavior
- observed behavior
- reproduction steps

## Known Non-Goals In This Version

- No enterprise SSO.
- No tenant-level encryption keys.
- No external WAF integration.
- No enterprise OIDC/SAML integration yet.
