-- EventRisk Phase I / ontology and analyst-review release readiness
-- Read-only. Execute against database eventrisk_factor_lab.
-- An approved mapping count is a necessary condition, not a sufficient
-- substitute for independent accuracy, causality, time, or license review.
WITH summary AS (
  SELECT
    (SELECT COUNT(*) FROM main.lab_event_factor_candidate_paths)
      AS candidate_paths,
    (SELECT COUNT(*) FROM main.lab_event_factor_candidate_paths
      WHERE review_status IN ('approved','accepted')
        AND NOT historical_mapping_lookahead)
      AS approved_nonhindsight_paths,
    (SELECT COUNT(*) FROM main.lab_event_factor_candidate_paths
      WHERE historical_mapping_lookahead)
      AS historically_lookahead_paths,
    (SELECT COUNT(*) FROM main.lab_relations)
      AS ontology_relations,
    (SELECT COUNT(*) FROM main.lab_relations
      WHERE status IN ('approved','accepted') AND evidence_id IS NOT NULL)
      AS approved_evidenced_relations,
    (SELECT COUNT(*) FROM main.lab_mapping_review_cases)
      AS sampled_review_cases,
    (SELECT COUNT(*) FROM main.lab_mapping_review_cases
      WHERE review_state IN ('approved','complete')
        AND reviewer IS NOT NULL
        AND reviewed_at IS NOT NULL
        AND analyst_decision IS NOT NULL
        AND evidence_url IS NOT NULL)
      AS completed_review_cases,
    (SELECT COUNT(*) FROM main.lab_evidence)
      AS evidence_records,
    (SELECT COUNT(*) FROM main.lab_factor_catalog
      WHERE license_class LIKE 'restricted%' AND active)
      AS active_restricted_factors,
    (SELECT COUNT(*) FROM main.lab_dataset_builds
      WHERE NOT regexp_full_match(source_commit,'[0-9a-f]{40}'))
      AS builds_without_full_git_sha
)
SELECT *,
  CASE
    WHEN active_restricted_factors > 0 THEN 'BLOCKED_LICENSE_GATING'
    WHEN approved_nonhindsight_paths = 0
      OR approved_evidenced_relations = 0
      OR completed_review_cases = 0
    THEN 'BLOCKED_UNREVIEWED_MAPPING'
    ELSE 'REQUIRES_INDEPENDENT_VALIDATION'
  END AS mapping_release_status
FROM summary;
