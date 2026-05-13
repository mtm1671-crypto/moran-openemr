import httpx

from app.target_client import TargetClient


def test_target_client_extracts_copilot_sse_final_event() -> None:
    body = "\n".join(
        [
            "event: status",
            'data: {"message": "retrieving evidence"}',
            "",
            "event: final",
            (
                'data: {"answer": "Safe refusal.", "citations": '
                '[{"evidence_id": "ev_1", "source_url": "/evidence/ev_1"}]}'
            ),
            "",
        ]
    )
    response = httpx.Response(
        200,
        headers={"content-type": "text/event-stream; charset=utf-8"},
        text=body,
    )

    text, citations, tool_outcome = TargetClient("http://localhost:8001")._extract_response_parts(
        response
    )

    assert text == "Safe refusal."
    assert tool_outcome is None
    assert citations[0].source_id == "ev_1"
    assert citations[0].url == "/evidence/ev_1"
