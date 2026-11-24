# Threat model

The trusted boundary is a locally controlled workstation and reviewed dataset inclusions. Public operation serves only static aggregates.

| Risk | Control and evidence |
| --- | --- |
| Untrusted catalog or file content | Verified official HTTPS host, bounded downloads, pinned digests, strict headers and row shape checks. Procedure fields and error codes are excluded from derivations. |
| Local data disclosure | Ignored raw and derived data, models and private state. Explicit tracked and static file allowlists, structured aggregate projection and hashes. |
| Bad model material | Trusted local versions only. Verify manifests, libraries and artifact hashes before loading JSON. No upload endpoint. |
| Malicious or unsupported API payload | Loopback bind, restricted Host and CORS, explicit POST origin checks, strict Pydantic fields, byte, batch and concurrency limits plus a whole-body deadline. Redacted validation errors. |
| Replay misuse or duplicate writes | One process-owned replay worker, per-output lock, short jobs, atomic job state, distinct interruption and cancellation states, verified seed manifests. |
| Local process or storage compromise | Treat writable registry and source manifests as privileged. Hashes detect corruption and accidental changes. A workstation controller can replace both content and local digests. |
| Public runtime cost or data access | Static export with explicit content security headers, reviewed aggregate identity and filesystem link checks. No deployed backend, web analytics, external API calls or metered bindings planned. |

The audit documents this release's file scope and local behavior. It does not attest endpoint hardening for production or independent security validation.
