# Explicit entity resolution

`againward/documents/resolution.py` operates on reviewed, source-local entity
occurrences. Model labels are scoped by source hash: two records called
`record-1` in different documents remain two entities.

A domain supplies `MatchPolicy`: comparable kinds, blocking keys, exact anchor
combinations, required scope, contradiction fields and cardinality. The resolver
indexes these keys, checks a bounded set of candidate pairs, and records exact
supporting and contradicting fact IDs. Prefix blocking can retrieve a candidate
but is never an exact anchor. No attributes are copied across a relationship.

States: CONFIRMED, CANDIDATE, AMBIGUOUS, REJECTED, CONTRADICTED. Confirmation by the
deterministic path requires reviewed exact anchors, matching required scope and
no contradictory identifiers. Multiple plausible targets demote an exclusive
match to AMBIGUOUS, including when one alternative is only a candidate.

Ambiguous links require a supplied HUMAN source review, hash-bound to the exact
resolution and citing supporting facts. Conflicting IDs require corrected evidence
and a new revision. The history retains the prior state and review hash.
The application cannot authenticate a reviewer's identity merely from a JSON role;
the operator must supply real approval. Synthetic tests label simulated reviews.

The policy is deliberately injected: off-hire, invoices and credit allocation
remain Rental vocabulary. Downstream adapters must explicitly require a confirmed
relationship before assigning a canonical foreign key. A score, description match
or convenient arithmetic cannot satisfy that check.

Tests in `tests/test_document_resolution.py` cover identifiers, ambiguous targets,
source-local labels, cardinality, order/noise invariance, bounded blocking and stale
review. The sparse fixture retrieves 100/100 intended pairs using 100 comparisons
among 200 records. This is not a measured recall guarantee on unseen client files.
