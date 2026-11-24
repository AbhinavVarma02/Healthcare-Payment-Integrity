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
| Synthetic role confusion | Commands enforce distinct analyst, reviewer, supervisor and operator permissions on loopback. The workstation operator controls role choice. Enterprise identity and multi-user isolation remain outside this local threat model. |
| Premature outcome visibility | The simulated clock and per-version availability gate receipt history and training. The historical evaluator stays outside the simulator namespace. |
| Workflow interruption or corruption | SQLite transactions, exact retries, reference-checked receipt replay and independent anchors cover accepted actions. Redacted rejections are bounded. A privileged workstation user can rewrite local data and digests. |
| Stale or incompatible candidate | Artifact and validation hashes, chronological split, lifecycle generation and explicit supervisor approval gate synthetic activation. A failed shadow retains the reference scoring path. |
| Tool misuse | Only typed analyst actions and reviewed evidence are available. Model experiments receive approved phrases without arguments or case contents. Release mode uses the deterministic tools. |

The audit documents this release's file scope and local behavior. It does not attest endpoint hardening for production or independent security validation.
