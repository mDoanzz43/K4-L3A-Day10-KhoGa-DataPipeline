from __future__ import annotations

from datetime import UTC, datetime

from core.config import load_settings
from core.utils import write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the reproducible baseline data, indexing, and evaluation pipeline."""
    settings = load_settings()

    records = []
    source_mode = "cached raw records"
    if not settings.refresh_source:
        records = load_raw_records(settings.paths.raw_records_json)
    if settings.refresh_source or not records:
        records = fetch_source_records(settings)
        source_mode = "Crossref API or offline snapshot"
    if not records:
        raise RuntimeError("No Crossref records are available for the baseline pipeline")

    clean_df = build_clean_dataframe(records, datetime.now(UTC))
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(
        clean_df,
        settings,
        settings.paths.freshness_report,
    )
    if not quality["success"]:
        raise RuntimeError(
            "Baseline data failed the quality gate; inspect "
            f"{settings.paths.baseline_quality_report}"
        )

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(clean_df, settings.paths.eval_testset)

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings,
        settings.paths.embeddings_json,
    )
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    source_summary = {
        "source": settings.source_api,
        "source_mode": source_mode,
        "query": settings.source_query,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "dropped_records": len(records) - len(clean_df),
        "embedding_model": settings.embedding_model,
        "chroma_collection": index.collection_name,
        "indexed_documents": index.collection.count(),
        "evaluation_questions": evaluation.summary["samples"],
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    print(f"Baseline pipeline complete: {len(clean_df)} clean papers")
    print(f"ChromaDB collection: {index.collection_name} ({index.collection.count()} documents)")
    print(f"Retrieval hit rate: {evaluation.summary['retrieval_hit_rate']:.4f}")
    print(f"Mean token F1: {evaluation.summary['mean_token_f1']:.4f}")
    print(f"Report: {settings.paths.baseline_report}")
