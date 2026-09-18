from benchmarking.rental import run_benchmark, benchmark_performance


def test_r01_r06_and_adversarial_cases(tmp_path):
    result = run_benchmark(tmp_path)
    assert result["passed"] == result["total"] == 13, result
    assert result["metrics"]["false_positives"] == 0
    assert result["metrics"]["false_negatives"] == 0
    assert result["cases"]["R06_ambiguous_return"]["resume"]["review_validated"]
    assert all(not p.name.startswith("scorer") for p in (tmp_path / "cases").rglob("*"))


def test_keyed_many_periods_without_false_positive():
    result = benchmark_performance((1000,))
    assert result["measurements"][0]["groups"] == 1000
    assert result["measurements"][0]["candidates"] == 0
