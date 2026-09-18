# Pre-migration Energy characterization

The ordinary SHA-256 fixtures were captured from `main` at `c27f261` on Termux
CPython 3.14. They remain unchanged. The v1 dataset fixture also remains unchanged.

CPython 3.12 changed floating-point `sum()` from its earlier left-fold algorithm.
GitHub CI uses CPython 3.11; only the demo JSON's low-order float digits differ.
The monthly JSON and both Markdown reports have identical hashes on both paths.

The `legacy_sum` fixtures were independently generated from `git archive c27f261
energy_mvp examples` in an isolated temporary directory, running the original
engine with the pre-3.12 left-fold addition algorithm. The resulting demo JSON hash
exactly matches the CPython 3.11 output observed in CI. No fixture is derived by
approving a modified engine's output and no numerical tolerance is added.

The characterization test exercises native summation and explicitly emulated
legacy summation; native CPython <3.12 uses the corresponding baseline fixture.
All checks remain exact byte/hash comparisons. Production Energy arithmetic is
unchanged by this migration or by this portability correction.
