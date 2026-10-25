#!/usr/bin/env python3
"""Shared-date, 48-security forward-holdout bootstrap research diagnostic.

Every security's baseline and joint-model *squared prediction loss* must use
the same strictly future held-out dates. Resample whole blocks of DATES, not
individual security rows: the market, Treasury and SOFR/EFFR shocks are shared
by all assets on a given date. Simultaneous 48-family bootstrap-t confidence
bounds are research uncertainty checks, NOT proven source PIT or beta releases.

This is a pure offline method. It cannot reconstruct historical out-of-sample
predictions from parent summary MSEs. Never infer forecasts or invent prices.
"""
from __future__ import annotations

from datetime import date, datetime
import math
import re

import numpy as np

ASSETS = 48
MIN_HOLDOUT_DATES = 150
BLOCK_OBSERVATIONS = 10
BOOT_RESAMPLES = 500
BOOT_SEED = 20261025
FAMILYWISE_ALPHA = 0.05
ASSET_KEY = re.compile(r"^[A-Z0-9._-]{1,32}$")
RESEARCH_ONLY = "SHARED_DATE_BOOTSTRAP_DIAGNOSTIC_NOT_INSTITUTIONAL"


def _day(value, label):
    if (not isinstance(value, date) or isinstance(value, datetime)):
        raise ValueError(f"{label}: source observed day must be date, not timestamp")
    return value


def validate(tickers, dates, train_last_date, baseline_squared_loss,
             joint_squared_loss):
    """Require one identical predeclared heldout calendar for all 48 assets.

    Loss input is not an authorization for the underlying forecasts. Forecast
    lineage must be independently established before a real run is trusted.
    """
    symbols = list(tickers)
    if (len(symbols) != ASSETS or len(set(symbols)) != ASSETS
        or any(not isinstance(s, str) or not ASSET_KEY.fullmatch(s) or
               s == "SPY" for s in symbols)
        or symbols != sorted(symbols)):
        raise ValueError("Expected 48 unique, sorted source security IDs excluding SPY")
    days = list(dates)
    if (len(days) < MIN_HOLDOUT_DATES or
        any(not isinstance(d, date) or isinstance(d, datetime) for d in days) or
        any(d1 >= d2 for d1, d2 in zip(days, days[1:]))):
        raise ValueError("Insufficient strictly ordered, shared holdout dates")
    cutoff = _day(train_last_date, "train_last_date")
    if cutoff >= days[0]:
        raise ValueError("Future holdout must start strictly after training cutoff")
    base = np.asarray(baseline_squared_loss, dtype=float)
    joint = np.asarray(joint_squared_loss, dtype=float)
    if (base.shape != (len(days), ASSETS) or joint.shape != base.shape or
        not np.isfinite(base).all() or not np.isfinite(joint).all() or
        np.any(base < 0) or np.any(joint < 0)):
        raise ValueError("Squared loss must be paired, finite, nonnegative and date-aligned")
    if np.any(base.mean(axis=0) <= 0):
        raise ValueError("Degenerate baseline squared loss invalidates skill")
    diff = base - joint
    if not np.isfinite(diff).all():
        raise ValueError("Nonfinite paired loss improvement")
    return symbols, days, cutoff, base, joint, diff


def assess(tickers, dates, train_last_date, baseline_squared_loss,
           joint_squared_loss):
    """Circular moving-block date bootstrap and simultaneous max-t bounds.

    Positive differences mean the four-factor joint model forecasts better
    than the market/Treasury-only comparator on the SAME heldout dates.
    Models, seeds and date windows must be predeclared before examining any
    real holdout outcomes. Normalizing bootstrapped deviations by per-asset
    bootstrap SE and using max |t| guards the entire 48-model family.
    """
    symbols, days, cutoff, base, joint, diff = validate(
        tickers, dates, train_last_date, baseline_squared_loss,
        joint_squared_loss)
    n = len(days)
    observed = diff.mean(axis=0)
    baseline_mean = base.mean(axis=0)
    skill = observed / baseline_mean
    rng = np.random.default_rng(BOOT_SEED)
    m = math.ceil(n / BLOCK_OBSERVATIONS)
    boot_means = np.empty((BOOT_RESAMPLES, ASSETS), dtype=float)
    offsets = np.arange(BLOCK_OBSERVATIONS, dtype=np.int64)
    for b in range(BOOT_RESAMPLES):
        # Entire 48-asset row is kept intact. Sampling assets independently
        # would create fictional independent macro shocks and spurious power.
        starts = rng.integers(0, n, size=m)
        idx = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)[:n]
        boot_means[b, :] = diff[idx, :].mean(axis=0)
    centered = boot_means - observed[None, :]
    se = boot_means.std(axis=0, ddof=1)
    if np.any(~np.isfinite(se)) or np.any(se <= 1e-12):
        raise ValueError("Degenerate date-block bootstrap uncertainty")
    max_t = np.max(np.abs(centered / se[None, :]), axis=1)
    threshold = float(np.quantile(max_t, 1 - FAMILYWISE_ALPHA))
    lower = observed - threshold * se
    upper = observed + threshold * se
    agg = float(observed.mean())
    agg_boot = boot_means.mean(axis=1)
    aggregate_lower = float(np.quantile(agg_boot, .025))
    aggregate_upper = float(np.quantile(agg_boot, .975))
    if not all(math.isfinite(x) for x in
               (threshold, agg, aggregate_lower, aggregate_upper)):
        raise ValueError("Invalid aggregate simultaneous holdout inference")

    return {
        "state": RESEARCH_ONLY,
        "forecast_pairs_are_source_verified": False,
        "original_issuer_price_vintages_verified": False,
        "funding_first_publication_pit_verified": False,
        "source_redistribution_rights_approved": False,
        "event_shock_causality_identified": False,
        "institutional_risk_model_released": False,
        "security_count": ASSETS,
        "independent_date_count": n,
        "asset_date_records_not_independent_shocks": n * ASSETS,
        "training_last_observed_date": cutoff.isoformat(),
        "heldout_first_observed_date": days[0].isoformat(),
        "heldout_last_observed_date": days[-1].isoformat(),
        "block_size_in_observation_days": BLOCK_OBSERVATIONS,
        "bootstrap_resamples": BOOT_RESAMPLES,
        "bootstrap_seed": BOOT_SEED,
        "familywise_alpha": FAMILYWISE_ALPHA,
        "simultaneous_max_t_critical": threshold,
        "cross_security_mean_loss_improvement": agg,
        "cross_security_mean_block_bootstrap_ci95": [
            aggregate_lower, aggregate_upper],
        "cross_security_mean_block_bootstrap_se": float(
            agg_boot.std(ddof=1)),
        "research_cells_with_positive_heldout_skill": int(np.sum(skill > 0)),
        "research_cells_with_simultaneous_lower_bound_above_zero": int(
            np.sum(lower > 0)),
        "security_diagnostics": [
            {
                "ticker": ticker,
                "paired_heldout_dates": n,
                "incremental_holdout_skill": float(skill[i]),
                "mean_baseline_minus_joint_loss": float(observed[i]),
                "simultaneous_lower_bound": float(lower[i]),
                "simultaneous_upper_bound": float(upper[i]),
                "statistical_research_screen_only": (
                    "RESEARCH_SIMULTANEOUS_48_FAMILY_SCREEN_PASS_NOT_INSTITUTIONAL"
                    if lower[i] > 0 else
                    "REJECT_SHARED_DATE_FAMILYWISE_HOLDOUT_UNCERTAINTY"
                ),
            }
            for i, ticker in enumerate(symbols)
        ],
    }
