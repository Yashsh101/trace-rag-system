from evals.run_eval import _threshold_failures


def test_eval_threshold_failure_is_reported():
    failures = _threshold_failures(
        {"retrieval_relevance": 0.5, "citation_correctness": 1.0, "no_answer_correctness": 1.0, "faithfulness": 1.0},
        {"retrieval_relevance": 0.8, "citation_correctness": 0.8, "no_answer_correctness": 0.9, "faithfulness": 0.8},
    )

    assert failures == ["retrieval_relevance=0.5 < 0.8"]
