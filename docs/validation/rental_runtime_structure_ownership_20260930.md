# Rental runtime structure ownership — 2026-09-30

## Failure boundary

The Phase 2 A receipts reached fact reconciliation with source-bound invoice
and line anchors, but one read omitted `entity_kind`. QA/reconciliation compared
that fragment as unknown/reference scope while the sibling read compared it as
a material invoice line. The fact union could therefore preserve the amount and
line reference while losing the line's structural kind. The later replay then
failed `ENTITY_METADATA_REQUIRED` on `entity_id` even though the exact same
source occurrence had been typed by the sibling read.

The B failure shape is an adjudication delta being checked before a complete
candidate is rebuilt from already established same-source structure. A delta
must not have to repeat metadata the runtime already has. This repair restores
only metadata supported by a sibling extraction with the same source ID and
source SHA, and only maps an entity kind through an explicit unique occurrence
anchor. It does not infer metadata from filenames, amounts, unrelated rows or
other sources. If neither read establishes a required field, validation still
stops; that is a real remaining completeness question, not a repair target.

## Ownership

| Data | Owner | Rule |
|---|---|---|
| Source ID/SHA, unit hash, native span, page/render binding | Runtime | Bound and revalidated against current bytes. |
| `entity_id` after a unique source-local occurrence anchor exists | Runtime | Stable hash of source ID, source SHA and explicit anchor. |
| `entity_id` / `entity_hint` emitted by a reader | Model hint only | Preserved in immutable parent extraction/assembly receipts; never an identity anchor in the selected state. |
| `entity_kind` | Source-supported structure | May be carried from an exact-hash sibling only when the same occurrence anchor is unique; otherwise required evidence remains missing. |
| `document_role` | Source-level structure | A unique exact-hash sibling observation may be retained at source scope. No filename-derived role. |
| `document_status` | Source-bound, potentially commercial | May be retained only as an exact same-source observation when unique. Conflicts are not selected by runtime. |
| Invoice/line/asset/agreement IDs, charge meaning, rate dimensions | Model-observed semantics | Exact source evidence and ordinary review remain required; runtime does not invent them. |

## Reconstruction boundary

`reconstruct_runtime_structure` is shared by fact reconciliation, adjudication
delta validation and persisted adjudicator observations. It accepts only
same-source, same-SHA peers. It preserves the candidate's evidence fields and
uses their exact native or visual bindings when constructing a runtime ID.
Source metadata is rebound to a source-scoped runtime ID; entity kinds are
attached only to exact, unique source-local anchors. Contradictory values remain
visible to the existing contradiction/completeness validators. The completed
extraction is validated before it can proceed to review; it does not promote
facts or open the calculation gate.

## Anticipated failure checks

Regression coverage now includes partial primary plus typed reread, adjudicator
delta reconstruction, exact-source/hash restrictions, metadata separated from
the row envelope, multiple rows without metadata leakage, unanchored entity
kind, and a conflicting document status. Existing calculation/package tests
continue to own the requirement that an incomplete or unreviewed package cannot
be calculated.

No CASE A/B end-to-end workflow was run for this change. A targeted isolated
inspection of the historical spreadsheet confirms it contains mirror rows and
row-level invoice/credit references; it does not provide an unambiguous
source-level lifecycle status. This change deliberately does not invent one.
