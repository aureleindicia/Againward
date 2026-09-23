# Rental privacy intake — active design (2026-09-23)

This is the pre-analytical gate for a managed real-client Rental workspace. It
does **not** make Codex local-only and does not authorize delivery. Contract
permission precedes the gate; business document analysis follows clearance.

## Measured starting point

At documentary HEAD `94d9d2a`, baseline pytest: **722 passed in 293.79 s**;
privacy/source subset: **88 passed in 14.14 s**. Ruff and configured mypy passed.
Five generated files were probed directly: native business PDF, native PDF with
professional contact, business raster scan, sensitive raster scan and hybrid
PDF. All five failed in `_scan()` with `ValueError: Format impossible à vérifier
avec confiance: .pdf.` A full privacy review on the clean native contract entered
`PRIVACY_BLOCKED`; no Rental business analysis was attempted. Root `AGENTS.md`
started at **38,051 bytes / 2,069 lines**.

## Current boundary

1. Codex remains the first substantive reader of `incoming/`. Python may stage
   copies without parsing before that review. The post-check is only a bounded
   privacy inspection, not a Rental extractor.
2. The injected `PreservationPolicy` now carries a separate risk profile.
   Legacy Energy remains strict. Rental permits ordinary professional email,
   phone, name and signature categories under `rental-b2b-risk-v1`.
3. The privacy-only inspector reuses the bounded PDF worker. It inspects every
   native page, PDF metadata and known component route. Images and raster pages
   require exact source-hash/version/component-bound `HUMAN` visual reviews.
   A model-only or missing review does not clear them. Hidden forms, annotations,
   named/active components and missing declared pages remain fail-closed unless
   their inspection path is explicitly supported.
4. Secrets, identity-document markers, medical and sensitive HR content cannot
   pass. Personal/private email labels and residential-address labels require
   minimization. A consumer-mail domain alone is not proof that a supplier
   contact is private. The review may declare additional categories; deterministic
   detection cannot be downgraded by a declaration.
5. The manifest records risk and business-confidentiality separately, with
   source hash, parser/inspection/policy versions and visual-review hashes.
   Commercial terms, rates and invoice amounts are not removed merely because
   they are client-confidential. PDF sanitation checks the retained native
   business markers and the removed value against visible text and metadata.
6. The approved derivative hash is bound to the manifest. A changed source,
   supplemental batch or risk-policy version requires revalidation. The Rental
   document adapter refuses non-analytical personal facts, so accepting a source
   does not automatically copy contacts into Rental EvidenceDataset rows.

## Visual review contract

For a new supervised case, use the local
[visual-review operator procedure](VISUAL_REVIEW_OPERATIONS.md) after Codex's
first privacy review. It renders only visual components into temporary
`privacy/candidate/`, asks the person at an interactive terminal to inspect
and attest each page, and binds the packet/preview/actor claim to the manifest.
It is not identity authentication; the owner must genuinely do the inspection.

Each image or PDF component requiring visual attention needs one closed entry:
`location`, `source_sha256`, `inspection_version`, `reviewer_role=HUMAN`,
`reviewed_at_utc`, `decision=PASS`, `detected_categories`,
`business_evidence_preserved=true`, `prompt_injection_ignored=true`.
The post-check validates structure and binding, not the human's eyesight or
identity. Test reviews are scripted synthetic fixtures; they are **not** real
human approvals or an empirical measure of vision sensitivity. A real client
must use an accountable reviewer and STOP if the component cannot be inspected.

## Known limits at this milestone

- Raster text is not OCR'd. A human visual decision can be wrong; no model
  accuracy is claimed. Metadata/known component checks are bounded, not a
  universal hostile-PDF sandbox.
- A sanitized PDF with visual business evidence is refused until preservation
  can be verified, rather than silently losing the image clause or signature.
- The generated document-intelligence corpus still has zero semantic recall
  without independent source-to-fact proposals. Privacy clearance is not
  semantic understanding or a recoverable financial claim.
- A single manual JSON visual review is not authenticated identity. Operational
  reviewer controls remain necessary before first real-client use.

See `docs/PRIVACY_ARCHITECTURE.md` for the inherited gate/lifecycle and
`docs/REAL_WORLD_ACCEPTANCE.md` for unfinished first-client criteria. The
synthetic measured privacy run and its limits are in
`docs/RENTAL_PRIVACY_BENCHMARKS.md`.
