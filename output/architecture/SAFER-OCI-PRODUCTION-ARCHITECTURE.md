# SAFER on Oracle Cloud — production architecture proposal

**26 October 2026 · Design proposal, not a deployment or production-readiness certification.**

This proposal makes OCI the hosting environment for SAFER, rather than a small destination icon in a delivery pipeline. It keeps the modular monolith and separates the public entry point, private compute, private data endpoints, regional managed services and recovery environment. Existing software is still local and synthetic-only; `APP_MODE=production` is rejected. No OCI resources, costs, public endpoints or real-data processing were activated by this work.

## 1. Decisions and constraints

The user delegated region and budget selection. The following are architect-selected planning decisions:

| Item | Decision |
|---|---|
| Primary region | India West (Mumbai), `ap-mumbai-1`, subject to service availability, capacity, residency and procurement approval |
| Recovery location | India South (Hyderabad), `ap-hyderabad-1`, for approved recovery copies and a reconstructable standby environment |
| Production budget | **₹75,000/month planning ceiling before tax**, including primary runtime and recovery storage; this is an allocation, not a provider quote or a claim that the bill of materials fits it |
| Free pilot | Separate existing proposal: one A1 VM, 2 OCPUs / 12 GB, synthetic data only |
| Core architecture | FastAPI modular monolith, React frontend, PostgreSQL; containers on Compute without Kubernetes |
| Production activation | Requires implementation, deployment testing, operational ownership and written real-data approval |

Do not change or assume the existing tenancy's home region. Subscription to the proposed production regions and actual service SKUs must be verified. If the itemized OCI estimate exceeds the ceiling, return a revised cost/design decision before provisioning; do not silently remove required redundancy. Second-region always-on compute is not included in this budget hypothesis. Faster regional recovery may require it and additional funding.

Oracle lists Mumbai and Hyderabad as **one availability domain each**. Therefore primary-region redundancy uses **different fault domains**, not fictional multiple availability domains. A region-wide outage requires the separate recovery region. [Region topology](https://docs.oracle.com/en-us/iaas/Content/General/Concepts/regions.htm)

## 2. What runs where

| Layer | Service | Deployment and responsibility |
|---|---|---|
| Name resolution | OCI DNS, or approved existing DNS | App and auth records point to the public load balancer; hosted DNS is not application traffic proxying |
| Public entry | OCI Flexible Load Balancer + regional WAF | HTTPS listener, hostname routing, backend health checks, request filtering and rate limiting; WAF is attached to the LB |
| Certificates | OCI Certificates / approved CA | Approved public certificate chain, private backend certificates and renewal monitoring; verify supported certificate issuance/import workflow |
| Network | OCI VCN, regional subnets, NSGs, Internet Gateway | Public LB subnet; private application and worker subnets; private data endpoints; default-deny service access |
| Application hosts | Two OCI Compute VMs, separate fault domains | Each runs pinned Nginx, FastAPI and Keycloak production containers with independent credentials, limits and volumes; app and auth have separate LB backend sets |
| Frontend | Nginx + React / TypeScript build | Serves versioned static assets and routes `/api/v1` to local FastAPI; Vite is a build tool, not the production web server |
| Business API | FastAPI / Pydantic / SQLAlchemy | FDR lifecycle, institution grants, evidence comparison, reminders, renewal, release, audit, exports; shared DB-backed sessions |
| Identity | Two clustered Keycloak nodes | OIDC code + PKCE, TOTP for privileged roles, approved federation and recovery; separate Keycloak PostgreSQL DB/user |
| Job execution | Two worker Compute VMs | Celery workers, bounded document parser and separately isolated ClamAV processes; one elected relay/scheduler with lease/fencing |
| Queue transport | OCI Cache, non-sharded Redis-compatible cluster, ≥3 nodes | TLS primary endpoint, retries/failover tests; job IDs only; Celery compatibility is a release gate |
| Durable state | OCI Database with PostgreSQL, ≥2 nodes | Application and Keycloak databases, separate roles, failover, backups and PITR; shared cluster is an explicit cost trade-off |
| Documents | Private OCI Object Storage | Exact document versions, quarantine and clean-state metadata, encryption, checksums; replaces SeaweedFS only after a proven migration |
| Key wrapping | OCI Vault / KMS | New adapter for the existing `KeyWrapper` contract; AES-GCM data encryption stays in application; wrapping key stays managed |
| Secrets | OCI Secret Management + scoped instance principals | Retrieve only permitted service credentials; restricted runtime files, renewal and rotation; no secrets in images, repo or `.env` |
| Oracle API routing | Service Gateway, with per-service endpoint validation | Private routing to supported OCI services; not every OCI API is assumed to support this path |
| Controlled outbound access | NAT Gateway + explicit egress proxy / allowlist | Patches, malware definitions and approved integrations; NAT alone is not a domain allowlist |
| Administration | OCI Bastion or approved VPN | Time-limited access; no permanent public SSH on private VMs; identity admin/health ports remain private |
| Email | OCI Email Delivery or approved Indian-resident SMTP service | Reminders only after sender/domain and processing approval; SPF/DKIM/DMARC, bounce handling; Mailpit stays in test |
| Operations | OCI Monitoring, Logging, Audit, Notifications | Infrastructure, app, LB/WAF and network signals; alert delivery and ownership; platform Audit does not replace application audit |
| Image delivery | GitHub Actions → OCI Container Registry (OCIR) | Tests, dependency/secret/image scans, SBOM and signed pinned digests; images must work on the selected VM architecture |
| Recovery | Hyderabad copies + independently administered backup compartment | DB recovery, immutable evidence bundles, object/version mapping, key/identity/config recovery and tested cutover |

OCI Cache documents TLS connections and recommends at least three nodes for HA. PostgreSQL HA uses a multiple-node system; enable and test PITR separately. [Cache guidance](https://docs.oracle.com/en-us/iaas/Content/ocicache/ocicachebestpractices.htm), [PostgreSQL HA](https://docs.oracle.com/en-us/iaas/Content/postgresql/high-availability.htm), [PITR](https://docs.oracle.com/en-us/iaas/Content/postgresql/point-time-recovery.htm)

## 3. Request and document flow

1. The institution opens the approved SAFER app hostname. DNS resolves the public LB address. Regional WAF policy applies at the LB; only HTTPS public traffic is admitted.
2. The LB sends app traffic to a healthy Nginx backend over verified TLS. Nginx serves the built React app; API requests go to the local FastAPI process. No VM or database needs a public IP.
3. Login redirects the browser to the separate auth hostname. That hostname reaches the Keycloak backend set. Code, state, nonce, PKCE, issuer and exact redirect checks remain enforced. Privileged roles require signed MFA assurance; authorization reads current local membership/grants.
4. A bounded upload enters quarantine. The API checks role, institution, content length, allowed type and idempotency. It encrypts bytes and writes the private object, obtaining its provider locator/version and integrity metadata. A DB transaction records a pending instrument/document and its outbox job. A reconciliation process handles an object written before a failed DB transaction; there is no fictitious transaction spanning PostgreSQL and Object Storage.
5. After commit, a leased relay publishes the job ID to OCI Cache. Workers claim durable PostgreSQL job state. At-least-once delivery requires idempotent claims/effects, bounded retries and reconciliation; a broker acknowledgement alone never changes an FDR's administrative status.
6. An isolated scanner receives bytes without database, object-store or KMS credentials. A separate parser sandbox has file/CPU/memory/time limits and no outbound network. Stale signatures, timeout or unavailable scanner keep the exact document version quarantined.
7. Extracted fields are proposals. Rules compare submitted claims, document extraction and separately recorded bank evidence, preserving the provenance of every value. Scanning or OCR never proves instrument authenticity.
8. A reviewer records scrutiny. Dates drive durable scheduled jobs and reminders. Release requires configured clearances and a competent approver, with version checks, audit and reconciliation. A request or model response cannot execute a bank refund.
9. Downloads pass application authorization and clean-state checks before exact-version decryption/streaming. No public bucket, unbounded pre-authenticated URL or direct public storage upload bypasses quarantine controls.
10. Redacted operational logs and request IDs support diagnosis. Immutable audit exports and manifests go to separately administered evidence storage. Monitoring pages the named owner for failed scans, queue age, access abuse, unhealthy nodes and backup freshness.

## 4. Network and trust boundaries

Illustrative private IPv4 plan; adapt to the organization's approved address inventory:

| Segment | Example CIDR | Permitted ingress |
|---|---|---|
| VCN | `10.42.0.0/16` | No flat allow-all rule |
| Public LB subnet | `10.42.0.0/24` | Internet TCP 443; Internet Gateway for the LB, not private hosts |
| Private app subnet | `10.42.10.0/24` | LB NSG to Nginx TLS backend only; Bastion target access by approved session |
| Private workers | `10.42.20.0/24` | No public ingress; narrowly scoped control/health access |
| Private data endpoints | `10.42.30.0/24` | PostgreSQL TLS from app/identity/worker roles; cache TLS from relay/workers |
| Private identity endpoints | Within app subnet, separate NSG / ports | Auth LB backend, approved internal OIDC and cluster peers only |

The production frontend and auth hostnames are placeholders, not registered domains. FastAPI can remain loopback inside each host's proxy boundary; cross-host calls use authenticated TLS. Keycloak cluster transport, management port and admin console are private. Configure only actual trusted proxy addresses, strip spoofed forwarded headers and test redirect/cookie behavior. [Keycloak proxy guidance](https://www.keycloak.org/server/reverseproxy)

Separate Docker networks restrict app, identity, job and scan traffic. Block untrusted scanner/parser containers from the OCI instance metadata endpoint as well as other networks; otherwise a nominally isolated parser could obtain the host instance principal. Separate Unix users, read-only images, capability drops, seccomp and resource limits reduce host-level risk. Containers sharing a VM do **not** have independent OCI instance identities: define dynamic-group policies for the whole trusted host and constrain per-container secret distribution. Stronger app/identity isolation requires dedicated identity hosts and an increased budget.

Service Gateway handles supported regional OCI service routes. Verify endpoint DNS and network reachability for Object Storage, Vault, Secrets, OCIR and telemetry individually. NAT is outbound only and must not turn into unrestricted LLM/file exfiltration. OCI WAF is LB-associated; it is not an additional app VM or a magic guarantee against every DDoS attack. [WAF deployment](https://docs.oracle.com/en/learn/oci-waf-flex-lbaas/)

## 5. Starting capacity and availability model

These are load-test inputs, not measured capacity or confirmed OCI SKUs:

| Pool | Starting hypothesis | Failure behavior |
|---|---|---|
| App/identity | 2 VMs, each about 2 OCPUs / 8 GB | One host drains/fails; the other must sustain the agreed peak workload, not only half the normal load |
| Workers/scanners | 2 VMs, each about 2 OCPUs / 8 GB | One worker host fails; jobs retry safely on surviving host; backlog drains after recovery |
| PostgreSQL | 2 supported managed nodes, SKU selected from current service menu | Primary failover; application reconnects with bounded retry; caller reconciles ambiguous writes |
| OCI Cache | ≥3 non-sharded nodes, minimum measured memory | Primary endpoint failover; committed job state recovered from PostgreSQL; no financial data cached |
| LB / Object Storage / Vault | Managed regional services | Service dependency degradation follows explicit fail-closed rules |

The four compute VMs alone require **8 OCPUs / 32 GB** under this hypothesis, before managed database/cache capacity. This cannot fit the 2 OCPU / 12 GB free pilot. Compute architecture, native libraries, image manifests and managed-service client compatibility must be tested before choosing Arm or x86. Avoid a Kubernetes control plane and microservice rewrite at this workload.

Keycloak uses production mode, two cluster members and persistent PostgreSQL storage. The selected Keycloak version's cluster discovery, cache replication, proxy settings and DB pool must be tested during member loss and restart. Separate app and identity databases/users on one managed HA cluster save cost but share maintenance, resource and outage domains; split clusters when workload or security requirements justify it. [Keycloak single-cluster architecture](https://www.keycloak.org/high-availability/single-cluster/introduction)

Proposed acceptance envelope: initially 100 authenticated concurrent sessions, 20 requests/sec mixed metadata traffic and 2 uploads/minute up to the configured 10 MiB cap. Reads p95 ≤500 ms, writes p95 ≤1 s, unexpected error rate <1%; scan completion is measured separately with queue time and signature updates included. Validate normal and one-host-down capacity, not just mocked/ASGI performance. Adjust these targets with AICTE's real workload before procurement.

## 6. Storage, encryption and evidence retention

The current SeaweedFS S3 implementation is not proven compatible with OCI. The target uses a provider-neutral storage interface plus an OCI adapter with instance-principal authentication, avoiding permanent user API keys where possible. A compatibility spike must cover exact version listing/read, content checksums, metadata, path/endpoint behavior, permissions and failure semantics. Do not assume S3 boto3 requests inherit instance-principal authentication. [OCI S3 compatibility](https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/s3compatibleapi.htm)

A document reference must bind provider, region, bucket, key, provider-version ID, ciphertext and plaintext integrity metadata as applicable, encryption context and immutable submission version. Moving a file changes provider version IDs; keep a signed/audited migration map and old references resolvable. Cross-region recovery must validate the same rule. No endpoint-only migration of frozen evidence.

Use separate bucket classes:

- **Document buckets:** private, versioned, encrypted, quarantine enforced by authoritative DB state. No financial documents in filenames, logs or image builds. New objects have unique keys; approved retention/deletion policy covers old versions.
- **Audit/evidence export buckets:** immutable unique-key bundles with approved retention rules, separate security ownership, verified hashes/manifests. Do not combine versioning and active retention rules on one bucket: OCI documents this incompatibility. Retention locking is irreversible and must not be enabled during a prototype or by a default script.
- **Recovery buckets:** separately administered encrypted bundles and manifests. Region copies alone are not protection against privileged deletion; prove independent access controls and recovery of decryption capability.

[Object retention constraints](https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/usingretentionrules.htm)

Envelope encryption keeps random data keys per object, encrypts bytes with AES-GCM and wraps the data key using a managed KMS key. The existing OpenBao interface is the local implementation; OCI KMS needs a new tested adapter and rewrap/migration/recovery process. Host disk or bucket encryption is additional protection, not a replacement for the application context/integrity contract. [OCI key management](https://www.oracle.com/security/cloud-security/key-management/)

Retrieve scoped secrets using instance principals and deliver only required runtime files; isolate migration credentials from application roles. Rotate credentials, revoke compromised sessions and test operation during rotation. Regional key availability, permitted key replication, chosen vault protection mode and recovery custody must be confirmed. Deleting a needed key can make intact backups permanently unreadable. [OCI Secrets](https://www.oracle.com/security/cloud-security/secrets/)

## 7. Recovery, SLOs and operational readiness

Targets below are business proposals, not inherited provider guarantees:

| Objective | Initial production gate |
|---|---|
| Application availability | 99.9% per calendar month; define eligible requests/maintenance and measure externally |
| Single app/identity host loss | Healthy host continues; target recovery/routing convergence ≤5 minutes under peak load |
| Regional disaster | Whole-system RPO ≤1 hour; RTO ≤4 hours, only after a successful timed recovery in Hyderabad |
| Queue operation | p95 queue age ≤120 seconds under accepted load; alert on sustained breach / dead jobs |
| Backup integrity | Daily verification, scheduled full recovery rehearsals and documented evidence; no stale or sole-copy acceptance |
| Security alert handling | Named on-call responder and tested notification/escalation path before public access |

Enable PostgreSQL PITR with a proposed 14-day recovery window, daily backups and approved India-region copies. PITR restores a new DB system and needs additional quota/capacity; test the cutover, not only backup creation. Logical corruption recovery is different from node failover. [PITR behavior](https://docs.oracle.com/en-us/iaas/Content/postgresql/point-time-recovery.htm)

A database backup alone does not meet whole-system RPO. Align DB checkpoints with exact object/version manifests, identity state, release policies, config/image digests and key recovery. Object copies and key versions must be available at the chosen DB recovery point. For a regional drill: fence the failed primary and senders, restore/verify identity and keys, restore DB/documents, reconcile uncertain external effects, verify login/MFA and clean document access, then approve DNS/LB cutover. Resume queues only after reconciliation. Avoid split-brain approvals or duplicate notifications/releases.

Cold rebuild using Terraform, image digests and backups is the baseline cost hypothesis. If capacity acquisition or key/object restoration cannot meet four hours, reserve warm capacity and reprice; do not advertise the RTO until proven. All recovery material, logs, documents and administrative custody remain in approved India locations. OCI location alone does not demonstrate procurement eligibility or legal compliance.

## 8. AI and external integrations

Gemini remains an external optional adapter, not a model hosted inside Oracle. It is disabled by default and not a dependency for submission, verification, renewal or release. Only the previously approved synthetic exception is eligible for testing. No real/anonymized data or metadata goes to a model until written data-owner, processing and residency approval. A regional OCI VM does not make a global API India-resident.

Use redacted structured facts, explicit source/access rechecks, bounded JSON validation, per-user/case budgets, timeouts and deterministic fallback. Prompt injection or generated wording cannot change authorization, classify evidence as confirmed or issue a release. Real bank verification remains pending formal authorization; label manual evidence and simulation accurately.

Mailpit stays a local test sink. Production email delivery needs approved sender credentials, receiver/minimum-content policy, domain authentication, bounce/suppression behavior and reconciliation of uncertain sends. Do not email document contents or sensitive FDR identifiers by default.

## 9. Delivery and incremental implementation backlog

| Phase | Concrete implementation | Acceptance evidence |
|---|---|---|
| P0 — authorize environment | Confirm region/tenancy inventory, account ownership, service SKUs, billing estimate, residency and data owner | Approved resource/cost sheet and named operators; synthetic-only until separately authorized |
| P1 — production config | Explicit production/synthetic-cloud modes; correct origins/issuer/proxy trust; non-dev Keycloak; internal TLS | Browser login/logout/CSRF/MFA/role tests through the actual LB; dev defaults rejected |
| P2 — cloud adapters | OCI object and KMS adapters; secret retrieval; audit export | Synthetic contract tests for exact versions, tamper denial, rotate/rewrap/recovery; migration mapping verified |
| P3 — infrastructure as code | VCN/subnets/NSGs, LB/WAF/certs, Compute pools, PG/cache, buckets/KMS, Bastion, gateways, logs and quotas | Reviewed Terraform plan; no destroy defaults; no public data ports or credentials; architecture-specific images verified |
| P4 — concurrency/reliability | Shared session checks, singleton relay lease/fencing, bounded pools, cache failover, idempotent external effects | Two-node failover tests, ambiguous-commit tests, one-host-down load test and queue replay without duplicate effects |
| P5 — delivery/observability | Signed images, OCIR, staged deployment, drain/rollback, dependency-aware health, monitoring and responder escalation | CI evidence, external synthetic checks, tested alarms, migration-compatible rollback rehearsal |
| P6 — disaster recovery | India-region DB/object/key/identity/config restoration and fenced cutover | Timed full drill meeting accepted RPO/RTO; verified exact references and no uncontrolled senders |
| P7 — launch acceptance | Independent security test, restore review, workload test, legal/procurement/data-owner acceptance | Signed readiness record, support/on-call ownership, training and incident runbooks |

No phase is marked implemented by this proposal. Existing `/health/ready` is only a DB check; add worker/broker/scanner/key readiness and user-visible degraded state without turning every optional dependency into a global outage. Key/object access failure blocks affected document operations; AI failure falls back; queue failure preserves committed pending work; telemetry failure triggers an alert without silently discarding mandatory audit.

Migration rollback is a data decision: preserve immutable evidence and database compatibility. Drain one app node at a time, use expand/contract migrations, one migration leader and digest-pinned previous releases. Never use `down -v`, destructive restore over primary, unreviewed provider-version rewriting or blanket tenant-admin credentials as a deployment shortcut.

## 10. Free pilot versus production

| Aspect | 2 OCPU / 12 GB pilot | Recommended production target |
|---|---|---|
| Purpose | SIH demonstration and synthetic validation | Approved institutional workload after readiness acceptance |
| Hosts | One A1 VM, local Compose stack | Redundant app/identity and worker hosts in separate fault domains |
| DB / queue | Self-hosted PostgreSQL / Valkey | Managed PostgreSQL HA / OCI Cache with verified Celery compatibility |
| Objects / keys | SeaweedFS / OpenBao locally, approved external backups later | OCI Object Storage / KMS adapters after migration proof |
| Availability | Single host failure stops the application; free capacity/reclamation risk | Defined SLO, fault-domain failover and separately tested regional recovery |
| Cost | Within verified account entitlements only | Paid OCI bill of materials; ₹75,000/month provisional ceiling before tax |
| Production claim today | No | No; target design pending P0–P7 implementation and acceptance |

Oracle currently documents 2 OCPUs / 12 GB equivalent A1 free entitlement and possible idle-resource reclamation. These constraints justify a pilot rather than a critical-production availability claim. Do not attempt to avoid reclamation by artificial CPU work. [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

## 11. Cost controls and unresolved commitments

Price the four VMs, block storage, two-node managed PostgreSQL (including its minimum supported shape), three-node Cache, LB bandwidth, WAF, DNS, certificate workflow, OCIR/image storage, object history and requests, log ingestion/retention, email, NAT/egress and Hyderabad recovery copies. Include recovery-test duplicates and temporary PITR DBs. Use current regional prices and actual billing currency; no invented exchange rate or claim that a free entitlement covers all services.

Budgets alert; they are not guaranteed hard spending stops. Apply compartment quotas, limited deployment privileges, tagged ownership, log/storage lifecycle budgets and reviewed scaling limits. Do not auto-delete documents, keys or the last known-good backup when a budget alarm fires.

Open commitments: existing home region/region subscriptions; actual service capacity and prices; managed DB extension/version compatibility; cache/client authentication and failover; object/key migration; approved public domains; SMTP and LLM processing approval; institution workload/retention; support and on-call ownership. These are launch gates, not reasons to blur the proposed architecture with what runs today.

## 12. Diagram conventions and artwork

The diagram's outer red boundary is the OCI tenancy; primary and recovery regions are distinct. The blue VCN boundary contains public and private subnet groupings. The right-hand managed-service column is regional and outside those subnet boxes. WAF/certificate symbols beside the public load balancer represent attached policy and certificate configuration, not extra VMs in that subnet. Cache and managed PostgreSQL are shown by their private client endpoints; service control planes remain managed by OCI. Dependency arrows are selective; network/IAM enforcement is defined in this document.

OCI service symbols come from the [official OCI Architecture Diagram Toolkit](https://docs.oracle.com/en-us/iaas/Content/General/Reference/graphicsfordiagrams.htm), converted from its draw.io library without redrawing the artwork. Technology artwork reuses the existing attributed logo collection. OCI Cache uses a generic database symbol because the bundled toolkit has no Cache-specific symbol; it is labelled explicitly. The diagram is an editable proposal, not evidence of deployed Oracle resources.
