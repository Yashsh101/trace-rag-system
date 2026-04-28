from types import SimpleNamespace

from app.services.llm_service import LLMService


class FakeResponses:
    def create(self, **kwargs):
        assert kwargs["model"]
        assert "SOURCE_CONTEXT" in kwargs["input"][1]["content"]
        return SimpleNamespace(
            output_text="The answer is supported by the source [S1].",
            usage=SimpleNamespace(input_tokens=10, output_tokens=8, total_tokens=18),
        )


class FakeClient:
    responses = FakeResponses()


def test_llm_service_returns_answer_and_usage():
    result = LLMService(client=FakeClient()).answer("Question?", "[S1] source text")

    assert result.answer.endswith("[S1].")
    assert result.total_tokens == 18

