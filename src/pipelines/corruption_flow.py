from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run corruption, trusted-raw repair, and three-state evaluation."""
    settings = load_settings()
    required_artifacts = (
        settings.paths.clean_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
    )
    missing = [str(path) for path in required_artifacts if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Run `python script/run_phase1.py` first. Missing: " + ", ".join(missing)
        )

    clean_df = pd.read_json(settings.paths.clean_json)
    corrupted_df = corrupt_clean_dataframe(
        clean_df,
        settings.paths.corruption_log,
    )
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(
        settings.paths.corrupted_clean_json,
        corrupted_df.to_dict(orient="records"),
    )

    corrupted_quality = run_data_quality_checks(
        corrupted_df,
        settings,
        "corrupted",
    )
    corrupted_freshness_path = (
        settings.paths.quality_dir / "corrupted_freshness_report.json"
    )
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        corrupted_freshness_path,
    )

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        settings.paths.corrupted_embeddings_json,
    )
    evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    corrupted_metrics = evaluation.summary
    hit_rate_drop = (
        baseline_metrics["retrieval_hit_rate"]
        - corrupted_metrics["retrieval_hit_rate"]
    )
    token_f1_drop = (
        baseline_metrics["mean_token_f1"] - corrupted_metrics["mean_token_f1"]
    )

    raw_records = load_raw_records(settings.paths.raw_records_json)
    repair_source = settings.paths.raw_records_json
    if not raw_records:
        raw_records = load_raw_records(settings.paths.raw_api_response)
        repair_source = settings.paths.raw_api_response
    if not raw_records:
        raise RuntimeError("Trusted raw snapshots contain no records; repair aborted")

    repaired_df = build_clean_dataframe(raw_records, datetime.now(UTC))
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(
        settings.paths.repaired_clean_json,
        repaired_df.to_dict(orient="records"),
    )

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness_path = (
        settings.paths.quality_dir / "repaired_freshness_report.json"
    )
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        repaired_freshness_path,
    )
    if not repaired_quality["success"]:
        raise RuntimeError(
            "Repair output failed the quality gate; inspect "
            f"{settings.paths.quality_dir / 'repaired_quality_report.json'}"
        )

    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        settings.paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_metrics = repaired_evaluation.summary

    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    print(f"Corrupted dataset: {len(clean_df)} -> {len(corrupted_df)} rows")
    print(f"Data quality gate passed: {corrupted_quality['success']}")
    print(f"Freshness SLA passed: {corrupted_freshness['is_fresh']}")
    print(
        "Retrieval hit rate: "
        f"{baseline_metrics['retrieval_hit_rate']:.4f} -> "
        f"{corrupted_metrics['retrieval_hit_rate']:.4f} "
        f"(drop {hit_rate_drop:.4f})"
    )
    print(
        "Mean token F1: "
        f"{baseline_metrics['mean_token_f1']:.4f} -> "
        f"{corrupted_metrics['mean_token_f1']:.4f} "
        f"(drop {token_f1_drop:.4f})"
    )
    print(f"Repair source: {repair_source}")
    print("\nMetric                 Baseline   Corrupted   Repaired")
    print("---------------------  --------   ---------   --------")
    for metric in (
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    ):
        print(
            f"{metric:<21}  "
            f"{float(baseline_metrics[metric]):>8.4f}   "
            f"{float(corrupted_metrics[metric]):>9.4f}   "
            f"{float(repaired_metrics[metric]):>8.4f}"
        )
    print(
        f"\nQuality gate           PASS       "
        f"{'PASS' if corrupted_quality['success'] else 'FAIL':<9}   "
        f"{'PASS' if repaired_quality['success'] else 'FAIL'}"
    )
    print(
        f"Freshness SLA          PASS       "
        f"{'PASS' if corrupted_freshness['is_fresh'] else 'FAIL':<9}   "
        f"{'PASS' if repaired_freshness['is_fresh'] else 'FAIL'}"
    )
    print(f"Comparison report: {settings.paths.comparison_report}")
