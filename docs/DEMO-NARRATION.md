# SAFER demo: narration with screen guide

Total length: about 6 minutes. Each segment gives the account to sign in with, the screen to open, the actions to take, and the narration to read.

**Before recording**
- Open http://localhost:5173 (use `localhost`, not `127.0.0.1`).
- Passwords are in `.local/demo-users.json`. Do not show that file on screen.
- Accounts: `alpha` and `beta` are institution officers. `auditor` is read-only. `reviewer` is the AICTE reviewer. `admin1` and `admin2` are access administrators.
- Reviewers and administrators must enroll a TOTP authenticator at first sign-in.
- Do not read or open the in-app "Demo guide" dialog. It still lists features as "next milestones".

---

## [0:00 · Introduction]

**Account:** none. Show the sign-in page.

**Screen:** Keycloak sign-in page at localhost:5173.

**Narration:**
SAFER is a portal for Secure Administration of FDRs through Electronic Review. It helps institutions submit fixed deposit records, lets independent reviewers check those records against evidence, and keeps a full audit trail of every step.

This demonstration uses synthetic data only. It does not move money and does not contact any bank.

---

## [0:30 · Deposit register]

**Account:** `alpha`.

**Screen:** **Deposit register** (home page). Point to the top bar, the overview cards, the search box and the records table.

**Narration:**
I'm signed in as an institution officer from Alpha. The header shows the institution and my role. The overview cards count records. Selecting a card lists the matching records.

I can search by bank name or FDR reference. The table shows each record's reference, bank, principal, maturity date and status.

---

## [1:30 · Creating a draft]

**Account:** `alpha`.

**Screen:** Deposit register. Click **New FDR** to open the **Add a new FDR** form.

**Actions:**
1. Enter the bank name, bank reference, principal amount (INR), issue date and maturity date.
2. Click **Save draft**.
3. Open the saved draft and click **Edit draft**, change a field, and save.
4. Reload the page to show the change persisted.

**Narration:**
To add a record, I select New FDR. I enter the bank, the bank reference, the principal amount in rupees, and the issue and maturity dates. The dates must be in order.

I save a draft. It is stored for my institution, and the change is recorded in the audit trail. I can reopen it and edit it. Saved changes remain after a reload.

---

## [2:30 · Documents]

**Account:** `alpha`.

**Screen:** The draft's detail page, **Supporting documents** section.

**Actions:**
1. Choose a document type.
2. Upload a small synthetic PDF, JPEG or PNG. It shows *Quarantined · scanning*, then *Scanned clean*.
3. Click **Download** on the scanned file.
4. Optionally, upload a renamed text file to show the rejection.
5. Point to the **Required before submission** list.

**Narration:**
Next I attach supporting documents. I choose the document type and upload a small synthetic file.

The file is quarantined and scanned for malware before anyone can download it. Once it is clean, it shows as scanned clean, and I can download it. Every upload and download is logged.

If a file's contents don't match its extension, the upload is rejected. The requirements list shows what is still missing before submission.

---

## [3:15 · Submission]

**Account:** `alpha`.

**Screen:** The draft's detail page, then the **Audit trail** section.

**Actions:**
1. Click **Submit metadata**.
2. Click **Confirm submission**. The record locks.
3. Scroll to the **Audit trail** timeline.

**Narration:**
When all requirements are met, I select Submit metadata and confirm. The record locks, so it can no longer be edited.

The audit trail lists each step, from the draft to the upload, scan, download and submission.

Submission sends the details for review. It does not prove that the bank is authentic.

---

## [3:45 · Isolation]

**Account:** Sign out, then sign in as `beta`.

**Screen:** Deposit register.

**Actions:** Show that Alpha's records are absent.

**Narration:**
Now I sign in as an officer from Beta. Beta cannot see Alpha's records. Each institution sees only its own data.

---

## [4:00 · Read-only auditor]

**Account:** Sign out, then sign in as `auditor`.

**Screen:** Deposit register. Open an Alpha record.

**Actions:** Point out that create and edit actions are not available.

**Narration:**
An auditor can open and read records but cannot create or change them. The edit and submit actions are not available to an auditor.

---

## [4:15 · Reviewer]

**Account:** Sign out, then sign in as `reviewer`. Complete TOTP enrollment if prompted.

**Screen:** **Review queue** → **Cases awaiting review** → open the Alpha case.

**Actions:**
1. Show the queue. Beta's cases do not appear.
2. Open the Alpha case.
3. Point to **Claim and independent evidence**, which shows Match or Mismatch for each field.
4. Enter independent evidence for a field.
5. Open the **Observations** section and raise an observation.
6. Open the **Bank confirmation simulator** and request a synthetic answer.

**Narration:**
Now I'm signed in as an AICTE reviewer. Reviewers and administrators must set up an authenticator app for two-factor sign-in.

The review queue shows submitted cases only from the institutions this reviewer covers.

I open the Alpha case. The claim table compares what the institution submitted with the document's values and with the independent evidence I enter. Each field shows Match or Mismatch.

If something needs an answer, I raise an observation. The bank confirmation simulator returns synthetic answers. Each answer is signed, and it is never treated as real bank confirmation.

---

## [5:15 · Institution responds]

**Account:** Sign out, then sign in as `alpha`. Then sign out and sign in as `reviewer` again.

**Screen:** The Alpha record's **Observations** thread.

**Actions:**
1. As `alpha`, reply to the observation.
2. As `reviewer`, open the same case and resolve the observation.

**Narration:**
The officer from Alpha sees the observation and replies in the thread. The reviewer then reviews the reply and resolves the observation.

---

## [5:25 · Access and release]

**Account:** `admin1`, then `admin2` to approve.

**Screen:** **Access management**.

**Actions:**
1. As `admin1`, grant authority to a reviewer. The grant appears under **Awaiting approval**.
2. Sign out, then sign in as `admin2` and approve the grant.
3. Show **Release policy versions** and the required clearances.
4. As an institution officer, open a case and use **Request release**.
5. As a reviewer, approve or reject the release request. Show the **Release decisions** list.

**Narration:**
Access changes need approval from a second administrator. I'm signed in as one administrator, who grants authority to a reviewer. A second administrator approves it.

Release policies set which clearances a release needs: a no-dues certificate, a closure or approval letter, a bank lien release, or an audit confirmation.

An institution can request a release. A reviewer can approve or reject it, and the institution can withdraw a request. Once approved, the release is recorded with the bank's evidence, such as a letter, an email from the bank's domain, the bank portal, or a call-back.

---

## [6:05 · AI assistance]

**Account:** `reviewer`.

**Screen:** Case review page. Point to the **Case summary** and **AI assistance** panels. Expand **Sources and versions**.

**Narration:**
The case summary and explanations are generated from local rules. Each statement links to its sources and their versions.

An optional AI wording mode exists, but it is disabled unless it is explicitly approved for synthetic data.

---

## [6:20 · Closing]

**Account:** Any.

**Screen:** Deposit register.

**Narration:**
SAFER separates institution claims from independent evidence. It keeps institutions, reviewers and auditors in separate roles. It scans every upload, and it records every change.

This is a prototype. It uses synthetic data, has no live bank integration, and makes no claim of production readiness. Thank you.

---

## Notes

- Button labels and panel names come from the source code. Confirm them in the browser before recording, because the wording may differ slightly.
- The release and access steps need the two administrator accounts and at least one prior release request. Prepare them before recording.
