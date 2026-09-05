# Goal C.1 — Adversarial review

## Attacks tested

- replacing an `ACT_NOW` recommendation claim by a no-action class: rejected;
- altering an economic value after model construction: rejected on render;
- omitting a decision card from a multi-decision model: rejected;
- inventing a no-action finding or a `what_we_checked` dataset reference:
  rejected;
- exposing paths or internal IDs in metadata, claim text, alternatives,
  constraints, sources or validation text: rejected;
- presenting a considered negative action as selected: rejected;
- treating mutually exclusive actions as an additive total: absent from the
  executive total and retained as explicitly non-additive alternatives.

## Residual risks

The client-facing language is intentionally authored by Codex. Structural
binding prevents a claim being attached to the wrong decision class, but cannot
prove that every stylistic phrase is persuasive or sufficiently specific. The
review process should therefore keep the report model and rendered PDF
inspection, rather than trust text generation alone.

No new diagnostic, physical-cause, economic-priority or scoring rule was added
in Goal C.1.
