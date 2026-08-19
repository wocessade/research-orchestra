"""离线测试用量 JSON 归一化。"""

from usage_scraper import _normalize_usage_payloads


def test_deepseek_platform_shape():
    cost = {
        "code": 0,
        "data": {
            "biz_data": [{
                "currency": "CNY",
                "total": [
                    {
                        "model": "deepseek-v4-pro",
                        "usage": [
                            {"type": "PROMPT_CACHE_HIT_TOKEN", "amount": "1.5"},
                            {"type": "RESPONSE_TOKEN", "amount": "2.5"},
                            {"type": "REQUEST", "amount": "0"},
                        ],
                    }
                ],
            }]
        },
    }
    amount = {
        "code": 0,
        "data": {
            "biz_data": {
                "total": [
                    {
                        "model": "deepseek-v4-pro",
                        "usage": [
                            {"type": "PROMPT_CACHE_HIT_TOKEN", "amount": "100"},
                            {"type": "RESPONSE_TOKEN", "amount": "50"},
                            {"type": "REQUEST", "amount": "3"},
                        ],
                    }
                ]
            }
        },
    }
    out = _normalize_usage_payloads(cost, amount)
    assert out["total_spending"] == "4.00"
    assert out["period_spending"] == "4.00"
    assert out["total_tokens"] == 150
    assert out["total_requests"] == 3
    assert out["models"][0]["name"] == "deepseek-v4-pro"


def test_zero_usage_month_accepted():
    """真·零用量月份: normalize 返回全 0, 不应被当成失败。"""
    cost = {"code": 0, "data": {"biz_data": [{"currency": "CNY", "total": []}]}}
    amount = {"code": 0, "data": {"biz_data": {"total": []}}}
    out = _normalize_usage_payloads(cost, amount)
    assert out["total_spending"] == "0"
    assert out["total_requests"] == 0
    assert out["models"] == []


if __name__ == "__main__":
    test_deepseek_platform_shape()
    test_zero_usage_month_accepted()
    print("OK: usage normalize")
