# Visual privacy review — controlled local operator procedure

Status: implemented protocol, **human rehearsal still required**. This is for
the owner's single-operator Termux/Android pilot, not remote identity proof.
The source must already have been staged under a reviewed contract, and Codex
must have been the first substantive reader of `incoming/`. Codex creates a
privacy `review.json` covering every file, with its first-reader attestations,
but does **not** fill a `HUMAN` visual review or approve a scan on behalf of a
person. No business extraction runs before clearance.

In an interactive Termux terminal:

```sh
python manage_investigation.py privacy-visual-prepare workspaces/CASE \
  workspaces/CASE/privacy/review.json
python manage_investigation.py privacy-visual-attest workspaces/CASE \
  workspaces/CASE/privacy/review.json --actor-id OWNER_LOCAL_ID
python manage_investigation.py privacy-validate workspaces/CASE \
  workspaces/CASE/privacy/review.json
```

`prepare` uses the bounded pre-clearance inspector. Native PDF text does not
require manual review merely for being PDF. For each image or visual PDF page
it creates a PNG/JPEG preview in `privacy/candidate/visual_previews/` and a
`visual_packet.json` with source hash, page, preview hash, parser version and
Rental policy version. It refuses unresolved forms/annotations/named or active
components, missing pages, bad render, oversized output and more than eight
visual components in one source. Ask for a safely re-exported or smaller source
instead of declaring such a file reviewed.

The operator must **open the exact preview and inspect all pixels**, including
small text, signatures, stamps, overlays and marginalia. The interactive
command then asks for the displayed source-hash prefix, PASS/REJECT, observed
privacy categories, and explicit confirmation that business evidence was
preserved and source-borne instructions ignored. REJECT/uncertainty means STOP;
do not type PASS to make the workflow continue. For a signed ordinary Rental
return, `PROFESSIONAL_SIGNATURE` is an acceptable category. Medical/HR-sensitive
material, secrets or unnecessary identity documents must be escalated, not
labelled as harmless. The preview itself is temporary sensitive content and
must not be copied into Git or a benchmark.

The command writes source-/preview-/policy-/packet-bound entries into the case
privacy review. The deterministic gate rechecks every hash and stores the
review hash plus claimed `reviewer_id` in the manifest. A changed source,
preview, packet or policy invalidates this decision. `privacy-validate` removes
temporary incoming/candidate material on successful clearance according to the
existing gate. The operator must confirm purge/retention separately.

This records an accountable local **claim**, not cryptographic authentication,
eyeball proof or machine-vision accuracy. The CLI refuses a non-TTY attestation,
but someone with local filesystem control could still forge JSON; the owner must
control device access and personally verify the rehearsal. Test fixtures use
scripted answers solely to test protocol invariants and never satisfy Gate B.
For client data, confirm the configured Codex/OpenAI processing permissions and
provider terms before submitting any document contents; local orchestration
does not make the model local.
