# SIH26265 — PPT ideas and speaker outline

Suggested project name: **NidhiSetu**

Suggested subtitle: **Security Deposit and FDR Lifecycle Management for AICTE**

Suggested pitch line: **Every deposit traceable. Every deadline actionable. Every decision accountable.**

Prepared 20 October 2026. This is a proposed six-slide storyboard, not a verified SIH 2026 national template. Preserve the headings, count, team identifiers and export requirements in the current official template supplied through SIH/your SPOC. Do not add slides if the actual format does not permit them.

## Slide 1 — Project identity and problem

Include problem ID 26265, the exact problem title, AICTE / Regulation Bureau, Software / Smart Automation, team details and NidhiSetu.

Use a restrained cover with one short lifecycle illustration or one cropped, genuine prototype screenshot. Do not use an AICTE logo to imply endorsement of your student project.

**Message:** AICTE needs a dependable view of deposit evidence, deadlines and authorised action.

**Opening speaker line:** “A deposit record is useful only when an officer can establish its evidence, next deadline and release status. NidhiSetu brings those three questions into one case history.”

## Slide 2 — Proposed solution and novelty

If the official template calls this “Idea/Solution,” include a compact problem-to-feature mapping:

| Operational concern | Proposed response |
|---|---|
| Unclear source of a value | Submitted, extracted and bank-confirmed values shown separately |
| Missed or unresolved actions | Deadline queue with owner and escalation |
| Replacement history difficult to follow | Linked instruments and coverage timeline |
| Release status unclear | Clearance, approval and execution tracked separately |

Use one horizontal process: **Submit → Review evidence → Monitor → Replace / Release**. Put three differentiators beside the relevant stages: field provenance, continuity assessment and decision evidence package.

**Suggested slide text:**

- Institution-wise repository with protected document versions.
- Evidence comparison and explainable discrepancy flags.
- Deadline monitoring, renewal history and authorised release tracking.

**Speaker emphasis:** AICTE already has online processes; your contribution is more reliable lifecycle coordination. Avoid the unsupported claim that AICTE currently has no FDR portal.

Research support: [AICTE e-governance RFP, JFDR](https://aicte.gov.in/sites/default/files/RFPeGov.pdf).

## Slide 3 — Technical approach

Use an editable architecture diagram with four obvious areas: user portals, application modules, private evidence/database storage and background/integration workers. Keep the bank connection visually separate and label it **Mock for prototype; authorised connection for deployment**.

Show a small technology line: React/TypeScript · Django API · PostgreSQL · Private object storage · OCR worker · Scheduled reminders.

Add one real prototype crop of the evidence workbench: an original document beside the claimed/extracted/confirmed comparison. If a prototype does not yet exist, label the image **proposed screen**, not “live system.”

**Speaker emphasis:** “OCR proposes values. Deterministic rules flag differences. Authorised officers make decisions. Bank confirmation remains a separate evidence source.”

Put detailed schemas, endpoints and rule logic in permitted backup material, not on the main slide.

## Slide 4 — Feasibility and viability

Use a three-row table, large enough to read:

| Risk | Plan |
|---|---|
| No production bank access during SIH | Labelled simulator, common adapter contract, authorised manual evidence route |
| Poor scans or missing fields | Confidence flags, original document review, correction history |
| Different policy rules and approval roles | Versioned rules and configurable authorised routing |

Include a short rollout line: **Synthetic prototype → Authorised pilot → One bank connection → Wider deployment**.

**Speaker emphasis:** the MVP works without pretending to have live access. Production integration needs formal agreements, security review and an approved policy register.

Research support: [HDFC FD API description](https://developer.hdfc.bank.in/fd-fetchfinancialinfo-v1), [CCA signature verification](https://www.cca.gov.in/index.php/signature_verification.html).

## Slide 5 — Impact and benefits

Use measured results once the prototype exists. Until then, label every number **target**.

Suggested evaluation tiles or a simple native chart:

- Target: at least 50% lower median officer handling time in a controlled comparison.
- Target: all expected reminders generated in the defined date test set.
- Target: all defined unauthorised release transitions blocked.

Keep raw OCR accuracy, human-reviewed field accuracy, notification delivery and overall bank-dependent verification time separate. Avoid a broad “99% accurate portal” statement.

Include one sentence of user benefit: **Institutions see pending actions; officers see evidence and deadlines; supervisors see the reasons cases are waiting.**

**Speaker emphasis:** “These are our test criteria. We will report the sample size, measured baseline and actual result.”

Do not invent AICTE loss estimates, backlog counts or time savings. Do not display a fictional before-and-after chart as research evidence.

## Slide 6 — Research and references

Use the space permitted by the official template. Keep source names readable and linked; speaker notes can hold full URLs and clause/page references.

Priority references:

1. [AICTE Approval Process Handbook 2024–27](https://aicte.gov.in/sites/default/files/APH%20Final.pdf) — applicability and administrative rules; verify later amendments.
2. [AICTE e-governance RFP](https://aicte.gov.in/sites/default/files/RFPeGov.pdf) — existing JFDR workflow context, historical document.
3. [HDFC FD API description](https://developer.hdfc.bank.in/fd-fetchfinancialinfo-v1) — bank-specific API feasibility, not access approval.
4. [CCA verification guidance](https://www.cca.gov.in/index.php/signature_verification.html) — digital-signature evidence.
5. [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) and [GIGW 3.0](https://guidelines.india.gov.in/new-features-of-gigw-3-0/) — secure and accessible design.

When the template allows it, include a prototype/repository/demo link. Otherwise place it only where permitted. Keep the full research report available separately.

## Optional backup material, only where permitted

- Role/access matrix and an example denied cross-institution request.
- State model showing independent verification versus administrative status.
- Replacement chain with a potential coverage gap.
- Release evidence checklist and required clearances.
- Controlled benchmark methodology and actual measurements.
- Cost assumptions and bank-integration dependencies.

Do not attach backup slides to a strict six-slide submission unless the official instructions allow it.

## Visual direction

Use the official template first. Within its permitted styling, use white space, navy text and one restrained teal accent. Use amber/red for unresolved actions together with text labels; colour alone must not communicate status.

Aim for 32-point slide titles and 20–24-point body text when the template permits. Use one primary visual per slide. Keep reference footers compact but readable. A real workbench screenshot will explain more than decorative images of money, locks or robots.

The most useful visuals are a lifecycle diagram, evidence comparison, renewal timeline, small architecture diagram and a genuine benchmark chart. Keep data charts, tables and diagrams editable.

## Three-minute speaking plan

| Time | Content |
|---|---|
| 0:00–0:20 | Define the officer's problem and introduce the project |
| 0:20–0:55 | Show the lifecycle and three differentiators |
| 0:55–1:35 | Explain evidence comparison and architecture |
| 1:35–2:10 | State the bank-access and policy constraints with feasible responses |
| 2:10–2:45 | Show measured results or clearly labelled targets |
| 2:45–3:00 | Close on evidence, next actions and accountable decisions |

Adjust to the actual allotted time. Rehearse with a timer and leave live demo time if the round permits it.

## Judge questions to prepare for

**How do you know an FDR is genuine?** We distinguish document checks from independent bank confirmation and record exactly which fields each source supports. OCR and a hash do not prove issuance.

**What if the bank has no API?** We preserve an approved manual confirmation route and keep unconfirmed facts visible. Production onboarding determines which channels are valid.

**What is innovative beyond reminders and CRUD?** Field-level evidence provenance, coverage across replacements, policy-version history and an exportable decision evidence package.

**Can the portal release money automatically?** The prototype records approved administrative steps and simulated execution evidence. Actual execution remains with authorised financial systems and procedures.

**How do you measure improvement?** Compare identical tasks against a measured manual baseline, disclose the sample and separate handling time from external bank waiting time.

**Why no blockchain?** The immediate requirement is controlled access, trustworthy source evidence and a traceable decision history. Protected audit checkpoints address tamper detection without introducing a distributed-network dependency.

## Ready-to-adapt abstract

NidhiSetu is a proposed Security Deposit and FDR Lifecycle Management Portal for AICTE's Regulation Bureau. It links institutional obligations with financial instruments, protected document versions, verification evidence and administrative actions. The portal distinguishes institution-submitted information from extracted values and independently confirmed bank facts, helping officers identify discrepancies without treating automated extraction as proof of authenticity. Configurable date monitoring assigns reminders and escalations, while linked replacement instruments preserve history and expose potential coverage gaps. Release requests move through authorised checks, clearances, decisions and execution reconciliation. Role-based access and a traceable event history support accountability. The SIH prototype will demonstrate the lifecycle using synthetic records and clearly labelled simulated bank responses. Evaluation will compare record quality, officer handling time, reminder coverage and release-control correctness against a documented test baseline. Production integrations remain subject to formal authorisation and applicable AICTE procedures.
