# Goal C.1 — Fidelity review

## Verified contract

- A report consumes persisted Goal A findings and Goal B decision records; it
  does not create a diagnosis or a decision.
- A decision card is bound to its decision, action (or considered action),
  findings, deterministic calculation and relevant constraints.
- A card recommendation has a controlled claim type compatible with the Goal B
  decision. This is structural fidelity, not an attempt by Python to infer the
  meaning of free French prose.
- No-action and `what_we_checked` client claims must resolve to real Goal A/B
  objects. A narrative string alone cannot introduce a checked fact.
- Exact and range economic displays are reconstructed from deterministic LOW /
  BASE / HIGH scenario results. HIGH is never promoted to an expected value.
- Rendering repeats model validation against the current case immediately
  before creating the PDF; post-build numeric/decision tampering is rejected.

## Multi-decision compatibility

Goal B supports its existing `decision` packet field and, when explicitly used,
the backward-compatible `decisions` list. A single action may not occur in two
competing client decisions. Goal C renders every selected positive decision and
every considered negative decision without aggregating their economics unless
Goal B's fail-closed portfolio contract permits it.

## Deliberate boundary

Python does not judge whether a sentence such as “ne faites rien” is natural
language contradictory. Instead it prevents this sentence from being the
structured recommendation claim of an `ACT_NOW` card: only
`ACTION_RECOMMENDED` can occupy that claim slot. Codex retains responsibility
for the wording and contextual explanation.
