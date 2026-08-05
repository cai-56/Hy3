from __future__ import annotations

import os

import pytest

from common import ApiConfig, create_client, thinking_body

pytestmark = pytest.mark.live


def test_live_basic_chat() -> None:
    if not os.environ.get("HY3_API_KEY"):
        if os.environ.get("HY3_REQUIRE_LIVE") == "1":
            pytest.fail("HY3_API_KEY is required because HY3_REQUIRE_LIVE=1")
        pytest.skip("HY3_API_KEY is not configured; live smoke was not run")
    config = ApiConfig.from_env()
    raw_response = create_client(config).chat.completions.with_raw_response.create(
        model=config.model,
        messages=[
            {
                "role": "user",
                "content": "Reply briefly to confirm the API is available.",
            }
        ],
        temperature=0,
        max_tokens=32,
        extra_body=thinking_body(False),
    )
    assert raw_response.status_code == 200
    response = raw_response.parse()
    assert response.model == config.model
    assert response.choices
    assert response.choices[0].message.content
