from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

STATE_CONFIG = {
    "Baseline": {
        "dataset": DATA / "clean" / "papers_clean.json",
        "metrics": DATA / "results" / "baseline_metrics.json",
        "answers": DATA / "results" / "baseline_answers.json",
        "quality": DATA / "quality" / "baseline_quality_report.json",
        "collection": "papers-baseline",
        "color": "#22c55e",
    },
    "Corrupted": {
        "dataset": DATA / "clean" / "papers_clean_corrupted.json",
        "metrics": DATA / "results" / "corrupted_metrics.json",
        "answers": DATA / "results" / "corrupted_answers.json",
        "quality": DATA / "quality" / "corrupted_quality_report.json",
        "collection": "papers-corrupted",
        "color": "#ef4444",
    },
    "Repaired": {
        "dataset": DATA / "clean" / "papers_clean_repaired.json",
        "metrics": DATA / "results" / "repaired_metrics.json",
        "answers": DATA / "results" / "repaired_answers.json",
        "quality": DATA / "quality" / "repaired_quality_report.json",
        "collection": "papers-repaired",
        "color": "#3b82f6",
    },
}


st.set_page_config(
    page_title="RAG Data Pipeline Observatory",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root {
        --bg: #0b1220;
        --surface: #162235;
        --surface-strong: #1d2c42;
        --border: #3b4b63;
        --text: #f3f6fa;
        --muted: #c1ccda;
        --accent: #2dd4bf;
        --accent-soft: #99f6e4;
        --warning: #fbbf24;
        --danger: #fb7185;
        --success: #4ade80;
      }
      html, body, [class*="css"], .stApp {
        font-size: 17px;
      }
      .stApp { background: var(--bg); color: var(--text); }
      [data-testid="stSidebar"] {
        background: #111c2d;
        border-right: 1px solid var(--border);
      }
      [data-testid="stSidebar"] * { color: var(--text); }
      [data-testid="stMarkdownContainer"],
      [data-testid="stMarkdownContainer"] p,
      [data-testid="stMarkdownContainer"] li,
      label, .stRadio label, .stSelectbox label {
        color: var(--text);
        line-height: 1.55;
      }
      h1, h2, h3, h4 { color: var(--text) !important; letter-spacing: -0.015em; }
      h1 { font-size: 2.35rem !important; }
      h2 { font-size: 1.75rem !important; margin-top: 1.1rem !important; }
      h3 { font-size: 1.25rem !important; }
      .hero {
        padding: 1.65rem 1.8rem; border-radius: 18px;
        background: #17263a;
        border: 1px solid #4b607a;
        border-left: 6px solid var(--accent);
        margin-bottom: 1.15rem;
      }
      .hero h1 { margin: 0; font-size: 2.4rem; color: #ffffff; }
      .hero p { color: #d4deea; margin: .55rem 0 0 0; font-size: 1.08rem; }
      .stage {
        min-height: 166px; padding: 1.15rem; border-radius: 14px;
        background: var(--surface); border: 1px solid var(--border);
      }
      .stage .num { color: var(--accent-soft); font-size: .85rem; font-weight: 800; letter-spacing: .09em; }
      .stage h3 { color: #ffffff !important; margin: .45rem 0; font-size: 1.12rem !important; }
      .stage p { color: var(--muted); font-size: .96rem; line-height: 1.48; margin: 0; }
      .pass { color: var(--success); font-weight: 800; }
      .fail { color: var(--danger); font-weight: 800; }
      .muted { color: var(--muted); }
      div[data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--border);
        padding: .9rem 1.1rem; border-radius: 12px;
      }
      div[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: 1rem !important; }
      div[data-testid="stMetricValue"] { color: #ffffff !important; font-size: 2rem !important; }
      div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 10px; }
      div[data-testid="stAlert"] {
        border: 1px solid #52647b;
        color: var(--text);
        font-size: 1rem;
      }
      div[data-baseweb="select"] > div,
      div[data-baseweb="input"] > div,
      textarea {
        background: var(--surface) !important;
        color: var(--text) !important;
        border-color: var(--border) !important;
      }
      button[kind="primary"] {
        background: var(--accent) !important;
        color: #06211d !important;
        font-size: 1rem !important;
        font-weight: 800 !important;
        border: 0 !important;
      }
      button[kind="secondary"] {
        background: var(--surface-strong) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        font-size: 1rem !important;
      }
      code, pre { font-size: .94rem !important; }
      .artifact-ok { color: var(--success); }
      .artifact-missing { color: var(--danger); }
    </style>
    """,
    unsafe_allow_html=True,
)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


@st.cache_data(ttl=3, show_spinner=False)
def load_dataframe(path_string: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    path = Path(path_string)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_json(path)


def dataframe_for(path: Path) -> pd.DataFrame:
    modified = path.stat().st_mtime_ns if path.exists() else 0
    return load_dataframe(str(path), modified)


def collection_counts() -> dict[str, int]:
    database = DATA / "chroma" / "chroma.sqlite3"
    if not database.exists():
        return {}
    query = """
        SELECT c.name, COUNT(e.embedding_id)
        FROM collections c
        JOIN segments s ON s.collection = c.id
        LEFT JOIN embeddings e ON e.segment_id = s.id
        GROUP BY c.name
    """
    try:
        with sqlite3.connect(database) as connection:
            return {name: int(count) for name, count in connection.execute(query)}
    except sqlite3.Error:
        return {}


def metric_payloads() -> dict[str, dict[str, Any]]:
    return {
        name: read_json(config["metrics"], {}) or {}
        for name, config in STATE_CONFIG.items()
    }


def quality_payload(state: str) -> dict[str, Any]:
    return read_json(STATE_CONFIG[state]["quality"], {}) or {}


def format_score(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def status_badge(value: bool) -> str:
    css = "pass" if value else "fail"
    label = "PASS" if value else "FAIL"
    return f'<span class="{css}">{label}</span>'


def run_pipeline(script_name: str, provider: str) -> tuple[int, str]:
    command = [sys.executable, str(ROOT / "script" / script_name)]
    environment = os.environ.copy()
    environment["LLM_PROVIDER"] = provider
    environment["REFRESH_SOURCE"] = "false"
    environment["REFRESH_TEST_SET"] = "false"
    output = st.empty()
    lines: list[str] = []
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        lines.append(line.rstrip())
        output.code("\n".join(lines[-35:]), language="text")
    code = process.wait()
    st.cache_data.clear()
    return code, "\n".join(lines)


def render_overview() -> None:
    st.subheader("Luồng dữ liệu end-to-end")
    stages = [
        ("01", "Crossref / Snapshot", "24 raw records và provenance bất biến"),
        ("02", "Cleaning", "Schema, dedup, age_days, embedding text"),
        ("03", "Quality Gate", "GX 1.x + Freshness SLA trước indexing"),
        ("04", "Vector Index", "MiniLM embeddings và ChromaDB"),
        ("05", "Evaluation", "Hit Rate, Token F1 và LLM Judge"),
        ("06", "Corruption", "6 lỗi có kiểm soát và đo suy giảm"),
        ("07", "Repair", "Rebuild idempotent từ trusted raw"),
    ]
    columns = st.columns(4)
    for index, (number, title, description) in enumerate(stages):
        with columns[index % 4]:
            st.markdown(
                f'<div class="stage"><div class="num">STAGE {number}</div>'
                f'<h3>{title}</h3><p>{description}</p></div>',
                unsafe_allow_html=True,
            )
            st.write("")

    metrics = metric_payloads()
    counts = collection_counts()
    st.subheader("Trạng thái hiện tại")
    for column, state in zip(st.columns(3), STATE_CONFIG):
        payload = metrics[state]
        quality = quality_payload(state)
        freshness = quality.get("freshness", {})
        with column:
            st.markdown(f"### {state}")
            st.metric("Indexed documents", counts.get(STATE_CONFIG[state]["collection"], 0))
            st.metric("Retrieval Hit Rate", format_score(payload.get("retrieval_hit_rate")))
            st.metric("Mean Token F1", format_score(payload.get("mean_token_f1")))
            st.markdown(
                "Quality " + status_badge(bool(quality.get("success"))) + " · Freshness "
                + status_badge(bool(freshness.get("is_fresh"))),
                unsafe_allow_html=True,
            )

    st.subheader("Quan hệ nhân quả cần trình bày khi demo")
    st.info(
        "Corruption làm thay đổi dữ liệu → GX/Freshness phát cảnh báo → retrieval và answer metrics suy giảm. "
        "Repair đọc lại trusted raw → validation PASS → metrics quay về baseline."
    )


def render_data_explorer() -> None:
    st.subheader("Data Explorer")
    state = st.radio("Chọn trạng thái dữ liệu", list(STATE_CONFIG), horizontal=True)
    frame = dataframe_for(STATE_CONFIG[state]["dataset"])
    if frame.empty:
        st.warning(f"Chưa có dataset cho trạng thái {state}.")
        return

    duplicate_count = int(frame["paper_id"].duplicated().sum()) if "paper_id" in frame else 0
    missing_summaries = int(frame.get("summary", pd.Series(dtype=str)).fillna("").eq("").sum())
    columns = st.columns(4)
    columns[0].metric("Rows", len(frame))
    columns[1].metric("Columns", len(frame.columns))
    columns[2].metric("Duplicate IDs", duplicate_count)
    columns[3].metric("Blank summaries", missing_summaries)

    left, right = st.columns([1.55, 1])
    with left:
        visible_columns = [
            name for name in ["paper_id", "title", "published", "age_days", "summary_chars"]
            if name in frame.columns
        ]
        st.dataframe(frame[visible_columns], width="stretch", height=390)
    with right:
        st.markdown("#### Phân bố tuổi dữ liệu")
        if "age_days" in frame:
            ages = pd.to_numeric(frame["age_days"], errors="coerce").dropna()
            bins = pd.cut(ages, bins=[-1, 30, 90, 180, 365, float("inf")], labels=["0–30", "31–90", "91–180", "181–365", ">365"])
            st.bar_chart(bins.value_counts(sort=False), color=STATE_CONFIG[state]["color"])
        if "summary_chars" in frame:
            st.markdown("#### Độ dài summary")
            st.bar_chart(frame["summary_chars"].value_counts().sort_index(), color="#38bdf8")

    st.markdown("#### Chi tiết một document")
    labels = frame["title"].fillna("Untitled").astype(str).tolist()
    selected = st.selectbox("Chọn paper", range(len(labels)), format_func=lambda index: labels[index])
    record = frame.iloc[selected].to_dict()
    first, second = st.columns(2)
    with first:
        st.json({key: record.get(key) for key in ["paper_id", "title", "authors_joined", "published", "categories_joined", "age_days"]})
    with second:
        st.text_area("text_for_embedding", str(record.get("text_for_embedding", "")), height=235)


def render_quality() -> None:
    st.subheader("Data Quality & Freshness Observatory")
    state = st.selectbox("Validation report", list(STATE_CONFIG))
    payload = quality_payload(state)
    if not payload:
        st.warning("Chưa có quality report cho trạng thái này.")
        return
    freshness = payload.get("freshness", {})
    stats = payload.get("statistics", {})
    cols = st.columns(5)
    cols[0].metric("Quality Gate", "PASS" if payload.get("success") else "FAIL")
    cols[1].metric("Checks", stats.get("evaluated_expectations", len(payload.get("results", []))))
    cols[2].metric("Checks passed", stats.get("successful_expectations", 0))
    cols[3].metric("Stale records", freshness.get("stale_rows", 0))
    cols[4].metric("Stale ratio", f"{float(freshness.get('stale_ratio', 0)):.1%}")

    results = []
    for item in payload.get("results", []):
        config = item.get("expectation_config", {})
        kwargs = config.get("kwargs", {})
        result = item.get("result", {})
        results.append(
            {
                "Expectation": config.get("type", "unknown").replace("expect_", ""),
                "Column": kwargs.get("column", "table"),
                "Status": "PASS" if item.get("success") else "FAIL",
                "Observed": result.get("observed_value", result.get("unexpected_count", "—")),
                "Unexpected %": (
                    f"{float(result['unexpected_percent']):.2f}%"
                    if result.get("unexpected_percent") is not None
                    else "—"
                ),
            }
        )
    st.dataframe(pd.DataFrame(results), width="stretch", hide_index=True)

    left, right = st.columns(2)
    with left:
        st.markdown("#### Freshness SLA")
        st.progress(min(float(freshness.get("stale_ratio", 0)), 1.0), text=f"Stale {float(freshness.get('stale_ratio', 0)):.1%} / giới hạn 25%")
        st.json(freshness)
    with right:
        rows = []
        for name in STATE_CONFIG:
            report = quality_payload(name)
            fresh = report.get("freshness", {})
            rows.append({"State": name, "Quality": int(bool(report.get("success"))), "Freshness": int(bool(fresh.get("is_fresh"))), "Stale ratio": float(fresh.get("stale_ratio", 0))})
        compare = pd.DataFrame(rows).set_index("State")
        st.markdown("#### So sánh tín hiệu")
        st.bar_chart(compare[["Quality", "Freshness"]], color=["#22c55e", "#38bdf8"])
        st.dataframe(compare, width="stretch")


def render_evaluation() -> None:
    st.subheader("RAG Evaluation")
    payloads = metric_payloads()
    metric_names = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]
    table = pd.DataFrame(
        {state: {metric: values.get(metric) for metric in metric_names} for state, values in payloads.items()}
    ).T
    st.dataframe(table.style.format("{:.4f}"), width="stretch")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Normalized metrics")
        normalized = table.copy()
        if "mean_judge_score" in normalized:
            normalized["mean_judge_score"] = normalized["mean_judge_score"] / 5.0
        st.bar_chart(normalized, color=["#22c55e", "#38bdf8", "#f59e0b", "#a78bfa"])
    with right:
        baseline = payloads.get("Baseline", {})
        corrupted = payloads.get("Corrupted", {})
        repaired = payloads.get("Repaired", {})
        delta = pd.DataFrame(
            {
                "Corruption delta": {m: float(corrupted.get(m, 0)) - float(baseline.get(m, 0)) for m in metric_names},
                "Repair vs baseline": {m: float(repaired.get(m, 0)) - float(baseline.get(m, 0)) for m in metric_names},
            }
        )
        st.markdown("#### Delta analysis")
        st.dataframe(delta.style.format("{:+.4f}"), width="stretch")

    state = st.selectbox("Xem câu trả lời chi tiết", list(STATE_CONFIG), key="answer_state")
    answers = read_json(STATE_CONFIG[state]["answers"], []) or []
    if not answers:
        st.warning("Chưa có answer artifact.")
        return
    selected = st.selectbox(
        "Câu hỏi",
        range(len(answers)),
        format_func=lambda index: f"{answers[index].get('id')} · {answers[index].get('question')}",
    )
    answer = answers[selected]
    c1, c2, c3 = st.columns(3)
    c1.metric("Retrieval hit", "YES" if answer.get("retrieval_hit") else "NO")
    c2.metric("Token F1", format_score(answer.get("token_f1"), 4))
    c3.metric("Judge", answer.get("judge", {}).get("score", "—"))
    st.markdown("**Ground truth**")
    st.write(answer.get("ground_truth", ""))
    st.markdown("**Agent answer**")
    st.write(answer.get("answer", ""))
    with st.expander("Retrieved document IDs và contexts"):
        st.json({"retrieved_doc_ids": answer.get("retrieved_doc_ids", []), "contexts": answer.get("retrieved_contexts", [])})


def render_corruption() -> None:
    st.subheader("Controlled Corruption & Idempotent Repair")
    log = read_json(DATA / "results" / "corruption_log.json", {}) or {}
    scenarios = log.get("scenarios", [])
    top = st.columns(3)
    top[0].metric("Input rows", log.get("input_rows", 0))
    top[1].metric("Output rows", log.get("output_rows", 0))
    top[2].metric("Scenarios", log.get("scenario_count", len(scenarios)))

    if scenarios:
        scenario_table = pd.DataFrame(
            [{"Type": item.get("type"), "Affected rows": item.get("affected_rows"), "Description": item.get("description")} for item in scenarios]
        )
        st.bar_chart(scenario_table.set_index("Type")["Affected rows"], color="#fb7185")
        st.dataframe(scenario_table, width="stretch", hide_index=True)
        for item in scenarios:
            with st.expander(f"{item.get('type')} · {item.get('affected_rows')} records"):
                st.write(item.get("description"))
                st.code("\n".join(item.get("paper_ids", [])), language="text")

    baseline = dataframe_for(STATE_CONFIG["Baseline"]["dataset"])
    corrupted = dataframe_for(STATE_CONFIG["Corrupted"]["dataset"])
    repaired = dataframe_for(STATE_CONFIG["Repaired"]["dataset"])
    st.markdown("#### Dataset state comparison")
    comparison = pd.DataFrame(
        {
            "Rows": [len(baseline), len(corrupted), len(repaired)],
            "Unique paper IDs": [df["paper_id"].nunique() if "paper_id" in df else 0 for df in [baseline, corrupted, repaired]],
            "Blank summaries": [int(df.get("summary", pd.Series(dtype=str)).fillna("").eq("").sum()) for df in [baseline, corrupted, repaired]],
        },
        index=["Baseline", "Corrupted", "Repaired"],
    )
    st.dataframe(comparison, width="stretch")


def render_control_center() -> None:
    st.subheader("Pipeline Control Center")
    st.warning("Các nút bên dưới ghi lại artifacts trong `data/`. Dùng provider `mock` để demo không cần API key.")
    provider = st.selectbox("LLM provider", ["mock", "gemini", "openai", "anthropic", "ollama"], index=0)
    key_map = {"gemini": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    required_key = key_map.get(provider)
    if required_key:
        configured = bool(os.getenv(required_key))
        st.caption(f"{required_key}: {'configured' if configured else 'not configured'}")

    left, right = st.columns(2)
    with left:
        st.markdown("### CP3 · Baseline")
        st.write("Raw → cleaning → GX/Freshness → MiniLM/Chroma → evaluation → report")
        if st.button("▶ Run baseline pipeline", type="primary", width="stretch"):
            with st.status("Đang chạy CP3...", expanded=True) as status:
                code, _ = run_pipeline("run_phase1.py", provider)
                if code == 0:
                    status.update(label="CP3 hoàn thành", state="complete")
                    st.success("Baseline pipeline thành công.")
                else:
                    status.update(label=f"CP3 thất bại · exit {code}", state="error")
                    st.error("Xem log phía trên để chẩn đoán.")
    with right:
        st.markdown("### CP4–CP5 · Corrupt & Repair")
        st.write("6 corruptions → alerts → degraded evaluation → trusted-raw repair → comparison")
        if st.button("▶ Run corruption & repair", type="primary", width="stretch"):
            with st.status("Đang chạy CP4–CP5...", expanded=True) as status:
                code, _ = run_pipeline("run_corruption_flow.py", provider)
                if code == 0:
                    status.update(label="CP4–CP5 hoàn thành", state="complete")
                    st.success("Corruption và repair pipeline thành công.")
                else:
                    status.update(label=f"CP4–CP5 thất bại · exit {code}", state="error")
                    st.error("Hãy chạy baseline trước và xem log.")

    st.markdown("#### Demo script gợi ý")
    st.code(
        "1. Overview: giới thiệu silent failure và 7 tầng pipeline\n"
        "2. Data Explorer: cho xem raw/clean contract và text_for_embedding\n"
        "3. Quality: baseline PASS, corrupted FAIL, repaired PASS\n"
        "4. Evaluation: chỉ ra Hit Rate 1.0 → 0.6 → 1.0\n"
        "5. Corruption: mở 6 scenarios và affected paper IDs\n"
        "6. Control Center: chạy live corruption/repair\n"
        "7. Kết luận: repair idempotent từ trusted raw",
        language="text",
    )


def render_artifacts() -> None:
    st.subheader("Artifact Registry")
    paths = [
        DATA / "raw" / "crossref_response.json",
        DATA / "raw" / "crossref_records.json",
        DATA / "clean" / "papers_clean.json",
        DATA / "eval" / "test_set.json",
        DATA / "embeddings" / "papers_embeddings.json",
        DATA / "quality" / "baseline_quality_report.json",
        DATA / "results" / "baseline_metrics.json",
        DATA / "results" / "corruption_log.json",
        DATA / "results" / "corrupted_metrics.json",
        DATA / "results" / "repaired_metrics.json",
        DATA / "reports" / "phase1_report.md",
        DATA / "reports" / "corruption_report.md",
    ]
    rows = []
    for path in paths:
        exists = path.exists()
        rows.append(
            {
                "Status": "READY" if exists else "MISSING",
                "Artifact": str(path.relative_to(ROOT)),
                "Size (KB)": round(path.stat().st_size / 1024, 1) if exists else 0,
                "Modified": pd.Timestamp(path.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S") if exists else "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    selected = st.selectbox("Preview artifact", [path for path in paths if path.exists()], format_func=lambda path: str(path.relative_to(ROOT)))
    if selected.suffix == ".md":
        st.markdown(selected.read_text(encoding="utf-8"))
    else:
        payload = read_json(selected)
        st.json(payload, expanded=False)


st.markdown(
    """
    <div class="hero">
      <h1>🔭 RAG Data Pipeline Observatory</h1>
      <p>Crossref → Quality Gate → Vector Search → Controlled Failure → Idempotent Recovery</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Demo Navigator")
    page = st.radio(
        "Section",
        ["Overview", "Data Explorer", "Quality & Freshness", "RAG Evaluation", "Corruption & Repair", "Control Center", "Artifacts"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Runtime")
    st.code(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\nLLM_PROVIDER={os.getenv('LLM_PROVIDER', 'mock')}", language="text")
    st.caption("Dashboard không hiển thị API key hoặc nội dung `.env`.")

renderers = {
    "Overview": render_overview,
    "Data Explorer": render_data_explorer,
    "Quality & Freshness": render_quality,
    "RAG Evaluation": render_evaluation,
    "Corruption & Repair": render_corruption,
    "Control Center": render_control_center,
    "Artifacts": render_artifacts,
}
renderers[page]()
