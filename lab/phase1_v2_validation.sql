-- EventRisk Phase I / factor-lab panel v2 structural acceptance
-- Read-only. Execute against MotherDuck database: eventrisk_factor_lab.
-- This is a deterministic integrity smoke test, not an independent model review.
-- An 'as_known' row is only a candidate for further audit if its underlying event
-- and factor availability histories have also been verified point-in-time.
WITH p AS (
  SELECT * FROM main.lab_event_factor_panel_v2
),
duplicates AS (
  SELECT COALESCE(SUM(n - 1), 0) AS duplicate_rows
  FROM (
    SELECT COUNT(*) AS n
    FROM p
    GROUP BY proposition_id, factor_id, observed_date, mode, research_run_id
    HAVING COUNT(*) > 1
  )
),
metrics AS (
  SELECT COUNT(*) AS total_rows,
    COUNT(DISTINCT proposition_id) AS propositions,
    COUNT(DISTINCT factor_id) AS factors,
    MIN(observed_date) AS first_event_date,
    MAX(observed_date) AS last_event_date,
    COUNT(*) FILTER (
      WHERE NOT isfinite(probability) OR probability < 0 OR probability > 1
    ) AS invalid_probabilities,
    COUNT(*) FILTER (
      WHERE event_cutoff_at::DATE <> observed_date
    ) AS misaligned_cutoffs,
    COUNT(*) FILTER (
      WHERE factor_observed_date > observed_date
    ) AS future_dated_factor_observations,
    COUNT(*) FILTER (
      WHERE factor_carried_forward <> (factor_observed_date < observed_date)
    ) AS invalid_carry_flags,
    COUNT(*) FILTER (
      WHERE factor_source_sha256 IS NULL OR LENGTH(factor_source_sha256) <> 64
    ) AS invalid_factor_hash_lengths,
    COUNT(*) FILTER (
      WHERE factor_daily_change IS NOT NULL
        AND previous_aligned_factor_value IS NOT NULL
        AND ABS(factor_daily_change -
          100 * (factor_value - previous_aligned_factor_value)) > 0.0001
    ) AS invalid_bps_changes,
    COUNT(*) FILTER (
      WHERE factor_available_at > event_cutoff_at
        AND NOT data_lookahead_warning
    ) AS unflagged_factor_lookahead,
    COUNT(*) FILTER (WHERE mode = 'retrospective') AS retrospective_rows,
    COUNT(*) FILTER (
      WHERE mode = 'as_known'
        AND factor_available_at <= event_cutoff_at
        AND NOT data_lookahead_warning
    ) AS potentially_as_known_rows
  FROM p
)
SELECT m.*, d.duplicate_rows,
  CASE WHEN m.invalid_probabilities = 0
      AND m.misaligned_cutoffs = 0
      AND m.future_dated_factor_observations = 0
      AND m.invalid_carry_flags = 0
      AND m.invalid_factor_hash_lengths = 0
      AND m.invalid_bps_changes = 0
      AND m.unflagged_factor_lookahead = 0
      AND d.duplicate_rows = 0
    THEN 'STRUCTURAL_CHECKS_PASSED'
    ELSE 'STRUCTURAL_CHECKS_FAILED'
  END AS structural_status,
  CASE WHEN m.potentially_as_known_rows = 0
    THEN 'BLOCKED_NO_POINT_IN_TIME_PANEL'
    ELSE 'REQUIRES_INDEPENDENT_PIT_AND_LICENSE_REVIEW'
  END AS research_release_status
FROM metrics AS m CROSS JOIN duplicates AS d;
