# Security Notes

## Threat model basics
- Untrusted uploads (video/zip) may attempt traversal or malformed data.
- API token leakage risk if tokens are stored client-side insecurely.
- Artifact links are signed and time-limited.

## Controls in this MVP
- Upload type and size validation at API boundary.
- ZIP extraction blocks absolute paths and `..` traversal, and only extracts allowed video extensions.
- API bearer auth supports JWT user sessions and hashed org API tokens.
- Tokens are stored hashed in DB, never in plaintext after creation response.
- Usage limits enforce monthly caps on minutes/jobs/exports.
- Object storage access uses presigned URLs for bounded-time retrieval.
