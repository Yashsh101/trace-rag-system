from pathlib import Path

from evals.run_eval import run_live_eval


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.base_url = kwargs.get("base_url")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def post(self, path, **kwargs):
        if path.endswith("/documents/ingest"):
            return FakeResponse({"job_id": "job-1"})
        return FakeResponse(
            {
                "query_log_id": 7,
                "answer": "Answer [S1].",
                "citations": [{"label": "S1", "filename": "doc.pdf", "page_start": 1, "page_end": 1}],
            }
        )

    def get(self, path):
        if path.endswith("/ingestion-jobs/job-1"):
            return FakeResponse({"status": "completed"})
        return FakeResponse({"retrieved_chunks": [{"filename": "doc.pdf", "page_start": 1, "page_end": 1}]})


def test_live_eval_runner_mock(monkeypatch, tmp_path):
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-test")
    monkeypatch.setattr("evals.run_eval.httpx.Client", FakeClient)

    predictions = run_live_eval(
        [{"id": "q1", "question": "What?", "document_path": str(doc), "expected_source_filename": "doc.pdf", "expected_page": 1}],
        api_url="http://test",
        **{"api_key": "key"},
        timeout=1,
    )

    assert predictions[0]["answer"] == "Answer [S1]."
    assert predictions[0]["retrieved"][0]["filename"] == "doc.pdf"
