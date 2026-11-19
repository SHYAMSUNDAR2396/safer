# SAFER architecture diagram plan

Draft · 26 October 2026 · based on application commit `eea1e14` and the existing technical-slide layout.

## Recommendation

Use a **C4-inspired application overview with a small numbered workflow overlay** for the main SIH technical-approach slide. Prepare separate security/data-flow and deployment diagrams for technical questions. Add a focused AI sequence diagram if explaining the new LLM integration is part of the pitch.

This combination answers four distinct questions: what exists, how an FDR moves through it, where sensitive information crosses boundaries, and where the software would run. Keep the four views separate rather than putting all their detail into one picture.

The main illustration is a presentation adaptation, not a strict UML diagram or formal DFD. Its legend must say so. C4's term “container” means an application or data store; it does not automatically mean a Docker container. Domain modules inside the FastAPI application must not look like separately deployed microservices.

## Basis and sources

The supplied [GeeksforGeeks article](https://www.geeksforgeeks.org/system-design/how-to-draw-architecture-diagrams/) distinguishes conceptual, component, deployment, sequence and data-flow views. Apply its emphasis on audience, boundaries, responsibilities, labelled connections and a legend. Its examples are guidance, not evidence of SAFER's implementation.

Use the primary [C4 container guidance](https://c4model.com/diagrams/container) for software structure and technology labels, [dynamic diagrams](https://c4model.com/diagrams/dynamic) for selected numbered interactions, [deployment guidance](https://c4model.com/diagrams/deployment) for environment-specific topology, and [notation guidance](https://c4model.com/diagrams/notation) for titles, legends and relationship labels.

Project evidence: `docs/ARCHITECTURE.md`, `docs/design/LLM-INTEGRATION.md`, `docs/design/OCI-ALWAYS-FREE-SCALING-PLAN.md`, Compose files, API routes and current prototype screens. Existing artwork in the workspace's `output/architecture/` is a layout starting point, not the current architecture authority.

## Diagram set

| View | Recommended type | Audience and question | Placement |
|---|---|---|---|
| 1. Main technical approach | C4-inspired application view + numbered workflow | SIH judges: how does SAFER solve the FDR lifecycle problem? | Main slide, L-shaped composition |
| 2. Sensitive information and authority | Level-1 DFD with trust boundaries | Security reviewers: who can access which records, and what can leave the system? | Appendix or architecture document |
| 3. Proposed Oracle prototype | Deployment view | Operators: what runs on the proposed 2-OCPU/12-GB VM, and what fails together? | Appendix, labelled proposal |
| 4. AI assistance | Sequence diagram with alternative outcomes | Technical judges: when is an LLM called, what does it receive, and how is its answer checked? | Optional appendix/detail frame |

A separate system-context diagram is useful for an introductory requirements document but adds limited value to the existing technical slide. An ER diagram belongs in database documentation. A class diagram is too detailed for the main slide.

## View 1: main-slide content and layout

Title: **SAFER — Secure FDR Lifecycle and Advisory AI**.

Use a master diagram at readable full-page scale first, then derive a shorter slide version. Keep the existing left technology strip outside the architecture's usable content rectangle. Within the remaining white space:

- Left vertical band: approximately 35–40% of usable width for actors, portal, backend and reviewer workflow.
- Bottom horizontal band: approximately 35–40% of usable height for persistent data, asynchronous processing and optional AI support.
- Upper-right area: two prototype screenshots, with captions **Institution submission** and **Reviewer case and evidence**. Fit actual aspect ratios; do not stretch screens.
- Keep a small title/status line and a legend. Test final dimensions against the actual PowerPoint slide; these percentages are composition proposals, not pixel measurements of an editable PPT.

This preserves the requested L shape while reserving screen space. Do not bend every dependency into the L: use short labelled connectors and references for supporting relationships.

### Actors and application structure

1. **Institution officer** — creates, submits and renews FDR records.
2. **AICTE reviewer / competent approver** — different grants; show separate role labels even if grouped visually.
3. **Access administrator / auditor** — supporting roles, shown compactly in the detailed master.
4. **Web portal — React + TypeScript**; Vite is the development/build tool.
5. **Authentication — Keycloak + Authlib**; OIDC authorization code + PKCE and privileged TOTP.
6. **Application — FastAPI + Pydantic**; one modular-monolith box with small module labels: intake/documents, evidence review, renewals/deadlines, release workflow.
7. **Case records — PostgreSQL + SQLAlchemy**; metadata, immutable submission references, grants, audit, job ledger and LLM usage reservations.
8. **Private documents — SeaweedFS/S3-compatible storage**; exact versions and hashes. Mark envelope encryption as the implemented readiness-profile capability, with OpenBao Transit as a supporting service.
9. **Background processing — PostgreSQL outbox → relay → Valkey → Celery**; the broker carries job IDs, while PostgreSQL owns job state. Add the isolated ClamAV scanner and local Mailpit notification capture as children of this group.
10. **Optional advisory wording — Gemini adapter**; external provider, off by default, with deterministic local fallback. Group this as an optional branch outside the core financial path.

For the slide, collapse supporting services into three labelled groups instead of squeezing ten equally sized boxes into the bottom band. The full master can show every service. Logos supplement readable labels; they must not replace responsibility text.

### Numbered business interactions

Use a short workflow ribbon separate from infrastructure dependency arrows:

1. **Capture** — validate institution-scoped metadata and accept document upload.
2. **Protect and inspect** — quarantine, version/hash, scan; clean status permits access but does not prove financial authenticity. Text extraction proposes values only.
3. **Submit** — require prescribed clean documents and freeze the submission snapshot with audit history.
4. **Review** — compare claims with separately recorded evidence; flag mismatches and unresolved observations for the reviewer.
5. **Monitor / renew** — configured reminders and replacement history; this is a branch, not a mandatory prerequisite for every release.
6. **Authorize release when eligible** — clearances, competent decision, instruction, recorded execution and reconciliation. Show as an alternative lifecycle branch; it is administrative tracking, not automatic movement of money.

The optional AI branch starts from an explicit reviewer action after authorized case access. Do not position it as the gate that determines financial verification or release eligibility.

Suggested connector labels: `same-origin JSON + session/CSRF`, `OIDC + PKCE`, `transactional records`, `private versioned object API`, `job IDs`, `scan bytes`, `advisory JSON`. Put exact protocol/transport labels in the detailed master; avoid claiming internal TLS on paths currently using local HTTP.

## View 2: security DFD

Show external people, a browser boundary, authenticated API processing, application data stores, the scanning boundary, the key-service boundary and the external model boundary. Keep formal DFD process/store notation consistent within this view.

Trace these separate data classes:

- Institution-submitted claims and frozen document versions.
- Recorded independent evidence versus labelled simulator results.
- Extracted text proposals versus accepted institution metadata.
- Scoped case metadata, audit events and administrative decisions.
- Minimized, operator-approved synthetic facts sent to Gemini only when enabled.
- Untrusted model wording returned for validation and human review.

Mark enforcement points: current role/institution grants, CSRF, document quarantine, source version/hash, privileged MFA, protected key files, source-digest approval, usage limits and post-generation revalidation. Do not draw a browser-to-database, browser-to-key-store or browser-to-Gemini connection.

Show ClamAV as isolated from database/object/key credentials. Show format-check/extraction processes as resource-limited; current shared UID/filesystem is not a complete sandbox. Separate security boundaries from the implementation-status legend so one dashed border does not have two meanings.

## View 3: deployment proposal

Title must include **Proposed Oracle private synthetic demo — not deployed**.

Draw one outer Indian-home-region OCI environment, conditional on region/account confirmation, containing one A1 VM labelled **proposed budget: 2 OCPUs / 12 GB RAM**. Place Docker Compose services inside that VM, distinguishing application, data and scanner networks. Include persistent volumes and the workstation/operator trust boundary.

Stage A access uses a restricted SSH tunnel and loopback browser origins. Show its existing Keycloak local identity volume separately. A later public-HTTPS/production-Keycloak/PostgreSQL identity design belongs in a separate Stage B frame or diagram; do not silently mix it into Stage A.

Show encrypted off-host backups and independent recovery material as proposed/conditional. Label one-VM failure scope and absence of HA. Do not add autoscaling, replicas, Kubernetes, a managed PostgreSQL service or a load balancer to make the drawing look more scalable. None is part of the accepted starting topology.

Keep the external Gemini provider outside the OCI boundary. Hosting the application in India does not establish where an external model processes data. Approval and live evaluation gates stay visible.

## View 4: AI sequence

Lifelines: reviewer/browser → FastAPI → PostgreSQL → provider adapter → Gemini. Represent the operator's approved-source file and credential as configuration references, not additional actors making runtime decisions.

Sequence:

1. Reviewer explicitly requests explain/summary; GET reads the authorized source package without inference.
2. POST validates session, MFA, role, assignment, CSRF and supplied source digest.
3. Check feature switch, synthetic egress consent, exact approved digest and protected key configuration.
4. Admit one cross-process request and persist conservative cost reservation.
5. Send a bounded, minimized structured package through the fixed HTTPS adapter.
6. Validate complete JSON, block identities and bounded text; attach server-owned facts and citations.
7. Recheck current session, grants, switches and source digest.
8. Display advisory wording beside deterministic facts; periodically revalidate displayed source access.

Use `alt` branches for disabled/unapproved/busy/budget/provider failure → local fallback, and changed/revoked access → discard/error. Keep the long provider call distinct from database reservation transactions. No model-generated arrow may point to approval, bank execution or an authoritative write.

## Visual language

- Blue: people, portal and application.
- Teal: data and completed core lifecycle responsibilities.
- Amber: asynchronous processing and pending work.
- Purple: optional AI support.
- Grey: external/proposed dependencies.
- Red: blocked/quarantined states only, not every security control.

Use badges/text for **Implemented**, **Off by default**, **Simulated**, **Proposed** and **Pending authorization**. Use numbered badges only for workflow ordering; separate line styles for request, asynchronous job and optional integration. Explain every style in the legend and keep meaning readable in greyscale.

Each primary box gets an icon, a short capability name and its technology underneath. Keep slide labels to two or three short lines. Test approximately 16–18pt minimum labels in the final slide export and move details to the master/appendix when they cannot fit. Tiny labels and intersecting arrows are layout failures, not reasons to shrink everything.

## Corrections required in the previous artwork

- Review, reminders, replacement and release tracking are now implemented; remove old blanket “planned” labels.
- Scan-only documents still require manual entry where no usable text layer exists; OCR is not configured.
- Real bank connectivity remains pending; the existing exchange is a labelled simulator. Recorded manual evidence is a separate path.
- Gemini integration exists but is off by default and has not passed live model evaluation.
- OpenBao envelope encryption, MFA and background outbox processing should be visible at the appropriate detail level.
- Oracle remains a proposed deployment. Do not add a cloud boundary to a current-local diagram as though it is already running there.
- Do not reuse older stack logos for TensorFlow, XGBoost, LangChain or other tools absent from the implementation.

## Build sequence and deliverables

1. Freeze the component/flow inventory against code and mark status/environment for every element.
2. Sketch the main C4-inspired view, then arrange its slide variant into the L-shaped space with real screenshot dimensions.
3. Build the security DFD and Oracle deployment view from the same inventory; add the AI sequence if included in the pitch.
4. Produce icon-assisted, editable Excalidraw source with independent text, shapes and connectors. Embed reusable image assets rather than depending on remote logo URLs.
5. Export SVG for sharp slide scaling and high-resolution PNG for compatibility. Supply Mermaid source for the sequence and a short legend/narration note.
6. Insert a copy into the technical-slide template, inspect at presentation size and compare labels/arrows with code. Preserve the original template and earlier artwork.

Suggested outputs under the existing workspace `output/architecture/` directory:

- `SAFER-v2-overview.excalidraw`, `.svg`, `.png`.
- `SAFER-v2-slide-fit.excalidraw`, `.svg`, `.png`.
- `SAFER-v2-security-data-flow.excalidraw`, `.svg`, `.png`.
- `SAFER-v2-oci-proposed-deployment.excalidraw`, `.svg`, `.png`.
- Optional `SAFER-v2-ai-sequence.mmd`, `.svg`.
- A slide-fit preview containing the diagram and two prototype screenshots.

Acceptance: a judge can identify the users, core stack, FDR path, evidence boundary and AI limitation within about 30 seconds; a developer can trace each labelled dependency; every future/simulated capability is labelled; diagrams are editable and readable at final slide size. These are review targets, not measured usability results.

This task drafts the diagram plan only. Actual Excalidraw, image exports and PPT editing are the next deliverables; no existing diagrams or application code were changed by this plan.
