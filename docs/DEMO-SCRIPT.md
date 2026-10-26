# SAFER demo video: script, screens, and function guide

Open first: http://localhost:5173 (use `localhost`, not `127.0.0.1`). Keep the browser at a standard width, and have `.local/demo-users.json` ready for passwords. Don't show that file on screen.

Target length: about 6 minutes. Each segment lists the sign-in account, the screen to open, and a narration line you can read or adapt.

Note: Don't read the in-app "Demo guide" dialog aloud. It still lists renewal, maturity alerts, release approvals and AI assistance as "next milestones", but those screens exist in the code.

---

## Segment 1: Introduction (0:00–0:30)

- **Screen:** Sign-in page (Keycloak login).
- **Account:** none yet.
- **Narration:** "SAFER is a portal for Secure Administration of FDRs through Electronic Review. It lets institutions submit fixed deposit records, lets independent reviewers check them against evidence, and keeps every step in an audit trail. This demo uses synthetic data only. It doesn't move money or contact a bank."

---

## Segment 2: Institution officer, deposit register (0:30–1:30)

- **Account:** `alpha` (institution officer).
- **Screen:** Deposit register (home page).
- **Narration:** "Alpha sees only its own institution's records."

| Function | Where | Say (about 10 seconds each) |
|---|---|---|
| Institution name, user, role | Top bar | "The header shows which institution and role you are signed in as." |
| Demo banner | Under the top bar | "The banner states that this is a synthetic prototype." |
| Overview cards | Above the table | "Cards count records by status. Clicking one lists the matching records." |
| Search | Records table | "Search finds a record by bank name or FDR reference." |
| Records table | Main panel | "Each row shows reference, bank, principal, maturity and status." |
| Load more | Table footer | "Long lists load page by page." |
| Demo guide | Sidebar | Skip, or mention it only briefly. |
| Sign out | Top-right icon | "Sign-out ends the app session." |

---

## Segment 3: Create and edit a draft (1:30–2:30)

- **Account:** `alpha`.
- **Screen:** Click New FDR, which opens the Add a new FDR form.
- **Narration:** "Officers enter the core FDR details."

| Field or button | Say |
|---|---|
| Bank name | "The bank the deposit is held with, for example Demo National Bank." |
| Bank reference | "The FDR number. Leading zeros are kept." |
| Principal amount (INR) | "A positive amount in rupees." |
| Issue date, maturity date | "Dates must be in order." |
| Obligation selector | "The form only allows obligations assigned to this institution." |
| Save draft | "Saves the draft and records it in the audit trail." |

Then open the saved draft and click **Edit draft** to show that changes are saved and persist after a reload.

---

## Segment 4: Documents: upload, scan and download (2:30–3:15)

- **Screen:** The draft's detail page, **Supporting documents** section.
- **Narration:** "Documents go through malware scanning before anyone can download them."

| Function | Say |
|---|---|
| Document type selector | "Choose what kind of document this is." |
| Upload | "Upload a small synthetic PDF, JPEG or PNG. It shows as *Quarantined · scanning* until it is clean." |
| Scan status | "Once the scan passes, it shows *Scanned clean*." |
| Download | "Downloads are logged." |
| Rejected file | "A renamed text file is rejected, because the content doesn't match its type." |
| Requirements list | "**Required before submission** lists what is still missing." |
| Read values from document | "A reader can pull values out of the document and use them to fill the form." |

---

## Segment 5: Submit and lock (3:15–3:45)

- **Screen:** Draft detail page.
- **Narration:** "Submitting sends the metadata for review. It does not prove the bank's authenticity."
- **Steps:** Click **Submit metadata**, read the confirmation, click **Confirm submission**. The record locks.
- **Show:** The **Audit trail** timeline, which lists upload, scan, download and submission events.
- **Show also:** The **Deadlines** and **Replacement and coverage** panels, if they appear. Explain them in one line: "Shows maturity deadlines and whether a replacement is needed."

---

## Segment 6: Isolation between institutions (3:45–4:00)

- **Account:** Sign out, then sign in as `beta`.
- **Screen:** Deposit register.
- **Narration:** "Beta can't see Alpha's records."

---

## Segment 7: Auditor, read-only (4:00–4:15)

- **Account:** `auditor`.
- **Screen:** Deposit register, then open an Alpha record.
- **Narration:** "Auditors can read records, but they can't create or change them. The Edit and Submit buttons are absent."

---

## Segment 8: Reviewer, case review (4:15–5:15)

- **Account:** `reviewer`. The first login asks for TOTP enrollment.
- **Screen:** Review queue → Cases awaiting review → open the Alpha case.

| Function | Say |
|---|---|
| Review queue | "Lists submitted cases from the institutions this reviewer covers. Beta's cases never appear here." |
| Claim and independent evidence table | "Compares what the institution claimed with the document and with the reviewer's own evidence. It shows Match or Mismatch." |
| Evidence entry | "Reviewers record evidence for each field separately." |
| Evidence log | "Each piece of evidence is listed with its source." |
| Observations | "Reviewers raise a point that needs an answer." |
| Thread | "The institution responds, then the reviewer resolves the observation." |
| Bank confirmation simulator | "Simulated answers for the demo. Each one is signed, and it never counts as real confirmation." |
| Institution documents | "The documents the institution uploaded." |

---

## Segment 9: Institution responds (5:15–5:25)

- **Account:** `alpha`.
- **Screen:** The record's **Observations** section.
- **Narration:** "The institution answers the observation. The reviewer then resolves it."

---

## Segment 10: Access management and release (5:25–6:05)

- **Account:** `admin1`. Then `admin2` to approve.
- **Screen:** **Access management**.

| Function | Say |
|---|---|
| Awaiting approval | "Authority changes need approval from a second administrator." |
| Grant authority | "Gives a reviewer or officer a scope and role." |
| Release policy versions | "Sets which clearances a release needs, such as a no-dues certificate, a closure letter, a lien release or an audit confirmation." |
| Release requests (on the case) | "Institutions request a release. Reviewers approve or reject it. Withdrawals are allowed." |
| Execution record | "After approval, the release is recorded with the bank's evidence: a letter, an email from the bank's domain, the bank portal, or a call-back." |

---

## Segment 11: AI assistance and explanations (6:05–6:20)

- **Account:** `reviewer`.
- **Screen:** Case review page, **AI assistance** and **Case summary** panels.
- **Narration:** "Explanations and summaries are generated from local rules, and each one links to its sources. An optional AI wording mode is off unless it is explicitly approved for synthetic data."

---

## Segment 12: Close (6:20–6:30)

- **Screen:** Deposit register.
- **Narration:** "SAFER keeps institutions, reviewers and auditors in separate roles, scans every upload, records every change, and separates what an institution claims from what has been independently verified. It is a prototype: no real bank data, no live bank integration, and no production claim."

---

## Quick function reference

| Area | Function | Who sees it |
|---|---|---|
| Access | Sign-in with Keycloak, MFA for reviewers and admins | Everyone |
| Register | Overview cards, search, record table, load more | Officers, auditors |
| Draft | New FDR, edit, save | Officers |
| Documents | Upload, malware scan, download, requirements check | Officers |
| Extraction | Read values from a document into the form | Officers |
| Submission | Submit metadata, lock record | Officers |
| Audit | Timeline of all events | Officers, auditors, reviewers |
| Deadlines and replacement | Maturity deadlines and replacement or coverage | Officers, reviewers |
| Review | Queue, case view, evidence, observations | Reviewers |
| Bank simulator | Signed synthetic bank responses | Reviewers |
| Access management | Grants, approvals, release policies | Admins |
| Release | Request, approve, reject, withdraw, execute with evidence, reconciliation | Officers, reviewers, admins |
| AI assistance | Case summary, source-linked explanations | Reviewers |
| Exports | Overview CSV export (protected) | Overview users |

---

**Not verified:** I read the screen code, not a live run. Check the exact button labels and the Overview metric names in the browser before recording. Those may differ slightly from this script.
