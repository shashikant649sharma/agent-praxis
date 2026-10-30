"""Unit tests for statistical integrity, effect-size calculation, and zero-variance detection."""

from __future__ import annotations

import numpy as np

from tools.run_p2_pilot import (
    cohen_d_paired,
    format_cohen_d,
    holm_bonferroni_adjust,
    paired_permutation_test_5,
)


def test_cohen_d_paired_constant_nonzero_difference_returns_none() -> None:
    """When all paired differences are constant and non-zero, std is zero.
    Cohen's d is undefined (division by zero) and must return None, NOT 0.0.
    """
    diffs = [0.85, 0.85, 0.85, 0.85, 0.85]
    result = cohen_d_paired(diffs)
    assert result is None, f"Expected None for constant non-zero differences, got {result}"
    assert format_cohen_d(result) == "N/A (zero variance)"


def test_cohen_d_paired_constant_zero_difference_returns_none() -> None:
    """When all paired differences are identical zeros, std is zero.
    Cohen's d is undefined and must return None.
    """
    diffs = [0.0, 0.0, 0.0, 0.0, 0.0]
    result = cohen_d_paired(diffs)
    assert result is None, f"Expected None for zero variance, got {result}"
    assert format_cohen_d(result) == "N/A (zero variance)"


def test_cohen_d_paired_near_zero_variance_returns_none() -> None:
    """Floating-point perturbation below 1e-9 should be guarded as zero variance."""
    diffs = [0.5, 0.5 + 1e-11, 0.5 - 1e-11, 0.5, 0.5]
    result = cohen_d_paired(diffs)
    assert result is None, f"Expected None for near-zero variance, got {result}"


def test_cohen_d_paired_insufficient_samples_returns_none() -> None:
    """Single sample has undefined sample standard deviation (ddof=1)."""
    assert cohen_d_paired([0.5]) is None
    assert cohen_d_paired([]) is None


def test_cohen_d_paired_valid_nonzero_variance() -> None:
    """Standard non-zero variance returns mathematically correct Cohen's d."""
    diffs = np.array([0.2, 0.4, 0.6, 0.8, 1.0])
    # mean = 0.6, std(ddof=1) = sqrt(0.1) ≈ 0.3162277
    # d = 0.6 / 0.3162277 ≈ 1.8974
    expected_d = round(float(np.mean(diffs) / np.std(diffs, ddof=1)), 4)
    result = cohen_d_paired(diffs)
    assert result is not None
    assert result == expected_d
    assert format_cohen_d(result) == f"{expected_d:.2f}"


def test_paired_permutation_test_5_exact_minimum_p_value() -> None:
    """For 5 strictly positive differences, exact two-tailed permutation p is 2/32 = 0.0625."""
    a = np.array([0.9, 0.8, 0.85, 0.95, 0.88])
    b = np.array([0.1, 0.1, 0.1, 0.1, 0.1])
    p_val = paired_permutation_test_5(a, b)
    assert p_val == 0.0625, f"Expected minimum two-tailed p=0.0625, got {p_val}"


def test_paired_permutation_test_5_identical_arrays_returns_one() -> None:
    """Identical arrays have zero observed difference, yielding p=1.0."""
    a = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
    b = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
    p_val = paired_permutation_test_5(a, b)
    assert p_val == 1.0


def test_holm_bonferroni_multiplicity_correction() -> None:
    """Holm-Bonferroni correction enforces family-wise error rate control."""
    p_vals = [0.0625] * 10
    adjusted = holm_bonferroni_adjust(p_vals)
    # 10 * 0.0625 = 0.6250 for all ranks
    assert len(adjusted) == 10
    for adj in adjusted:
        assert adj == 0.6250
