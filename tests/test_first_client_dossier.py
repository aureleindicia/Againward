"""The published eight-source DEV case is reproducible and keeps truth separate."""
from __future__ import annotations

import hashlib

import pytest

from benchmarking.first_client_dossier import generate


def test_eight_source_dev_dossier_is_reproducible_and_oracle_is_private(tmp_path):
    first = generate(tmp_path / "first")
    second = generate(tmp_path / "second")
    assert first["source_count"] == second["source_count"] == 8
    assert first["source_hashes"] == second["source_hashes"]
    public = tmp_path / "first" / "public" / "rental-eight-sources"
    private = tmp_path / "first" / "private" / "expected_after_review.json"
    assert private.is_file() and private.parent not in public.parents
    assert {path.name for path in public.iterdir()} == set(first["source_hashes"])
    assert all(hashlib.sha256((public / name).read_bytes()).hexdigest() == digest
               for name, digest in first["source_hashes"].items())
    assert (public / "signed_return_scan.pdf").read_bytes().startswith(b"%PDF")
    with pytest.raises(ValueError, match="already exists"):
        generate(tmp_path / "first")
