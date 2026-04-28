import argparse
import json
import re
import time
from pathlib import Path
from statistics import mean

import httpx

NO_ANSWER_TEXT = "i could not find this in the uploaded documents"
CITATION_RE = re.compile(r"\[(S\d+)\]")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate_case(golden: dict, prediction: dict) -> dict:
    answer = prediction.get("answer", "")
    citations = prediction.get("citations", [])
    retrieved = prediction.get("retrieved", [])
    should_answer = bool(golden.get("should_answer", True))

    expected_source = golden.get("expected_source_filename")
    expected_page = golden.get("expected_page")

    retrieval_relevant = _contains_expected_source(retrieved, expected_source, expected_page) if should_answer else True
    citation_correct = _contains_expected_source(citations, expected_source, expected_page) if should_answer else len(citations) == 0
    no_answer_correct = (NO_ANSWER_TEXT in answer.lower()) is (not should_answer)
    faithfulness = _faithfulness_heuristic(answer, citations, should_answer)

    return {
        "id": golden["id"],
        "retrieval_relevance": float(retrieval_relevant),
        "faithfulness": float(faithfulness),
        "citation_correctness": float(citation_correct),
        "no_answer_correctness": float(no_answer_correct),
    }


def summarize(scores: list[dict]) -> dict:
    metric_names = ["retrieval_relevance", "faithfulness", "citation_correctness", "no_answer_correctness"]
    return {
        "case_count": len(scores),
        **{metric: round(mean(score[metric] for score in scores), 4) if scores else 0.0 for metric in metric_names},
    }


def run_live_eval(dataset: list[dict], api_url: str, api_key: str, timeout: float) -> list[dict]:
    headers = {"X-API-Key": api_key}
    predictions: list[dict] = []
    with httpx.Client(base_url=api_url.rstrip("/"), headers=headers, timeout=timeout) as client:
        document_paths = sorted({case["document_path"] for case in dataset if case.get("document_path")})
        for document_path in document_paths:
            with Path(document_path).open("rb") as handle:
                response = client.post("/api/v1/documents/ingest", files={"file": (Path(document_path).name, handle, "application/pdf")})
                response.raise_for_status()
            job_id = response.json()["job_id"]
            _wait_for_job(client, job_id, timeout)

        for case in dataset:
            response = client.post("/api/v1/query", json={"question": case["question"]})
            response.raise_for_status()
            payload = response.json()
            trace = _fetch_trace_for_response(client, payload.get("query_log_id"))
            predictions.append(
                {
                    "id": case["id"],
                    "answer": payload.get("answer", ""),
                    "citations": payload.get("citations", []),
                    "retrieved": trace.get("retrieved_chunks", []),
                }
            )
    return predictions


def _wait_for_job(client: httpx.Client, job_id: str, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/v1/ingestion-jobs/{job_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["status"] == "completed":
            return
        if payload["status"] == "failed":
            raise RuntimeError(f"Ingestion job failed: {payload.get('error_message')}")
        time.sleep(1)
    raise TimeoutError(f"Ingestion job timed out: {job_id}")


def _fetch_trace_for_response(client: httpx.Client, query_log_id: int | None) -> dict:
    if query_log_id is None:
        return {"retrieved_chunks": []}
    response = client.get(f"/api/v1/query/{query_log_id}/trace")
    response.raise_for_status()
    return response.json()


def _contains_expected_source(items: list[dict], expected_source: str | None, expected_page: int | None) -> bool:
    if expected_source is None:
        return True
    for item in items:
        filename = item.get("filename") or item.get("source_filename")
        if filename != expected_source:
            continue
        page_start = item.get("page_start") or item.get("page")
        page_end = item.get("page_end") or page_start
        if expected_page is None or (page_start is not None and int(page_start) <= int(expected_page) <= int(page_end)):
            return True
    return False


def _faithfulness_heuristic(answer: str, citations: list[dict], should_answer: bool) -> bool:
    if not should_answer:
        return NO_ANSWER_TEXT in answer.lower()
    cited_labels = set(CITATION_RE.findall(answer))
    citation_labels = {citation.get("label") for citation in citations}
    return bool(answer.strip()) and bool(cited_labels) and cited_labels.issubset(citation_labels)


def _threshold_failures(summary: dict, thresholds: dict[str, float]) -> list[str]:
    return [f"{metric}={summary.get(metric, 0.0)} < {threshold}" for metric, threshold in thresholds.items() if summary.get(metric, 0.0) < threshold]


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG eval runner")
    parser.add_argument("--dataset", required=True, help="Path to golden JSONL")
    parser.add_argument("--predictions", help="Path to prediction JSONL from the API")
    parser.add_argument("--api-url", help="Live API URL, e.g. http://localhost:8000")
    parser.add_argument("--api-key", help="API key for live mode")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--min-retrieval-relevance", type=float, default=0.80)
    parser.add_argument("--min-citation-correctness", type=float, default=0.80)
    parser.add_argument("--min-no-answer-correctness", type=float, default=0.90)
    parser.add_argument("--min-faithfulness", type=float, default=0.80)
    args = parser.parse_args()

    dataset = load_jsonl(Path(args.dataset))
    if args.api_url:
        if not args.api_key:
            raise SystemExit("--api-key is required with --api-url")
        predictions = run_live_eval(dataset, args.api_url, args.api_key, args.timeout)
    elif args.predictions:
        predictions = load_jsonl(Path(args.predictions))
    else:
        print(f"Loaded {len(dataset)} golden cases.")
        print("Mock mode: provide --predictions or --api-url/--api-key to compute gates.")
        return

    predictions_by_id = {row["id"]: row for row in predictions}
    scores = [evaluate_case(case, predictions_by_id.get(case["id"], {"answer": "", "citations": [], "retrieved": []})) for case in dataset]
    summary = summarize(scores)
    print(json.dumps({"summary": summary, "cases": scores}, indent=2))
    failures = _threshold_failures(
        summary,
        {
            "retrieval_relevance": args.min_retrieval_relevance,
            "citation_correctness": args.min_citation_correctness,
            "no_answer_correctness": args.min_no_answer_correctness,
            "faithfulness": args.min_faithfulness,
        },
    )
    if failures:
        raise SystemExit("Eval gates failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
