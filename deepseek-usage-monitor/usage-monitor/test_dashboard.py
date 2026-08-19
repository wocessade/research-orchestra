"""Test dashboard render on e-ink display."""
import sys, os
sys.path.insert(0, '/home/liuxfs/usage-monitor')
sys.path.insert(0, '/home/liuxfs/usage-monitor/waveshare_epd')
os.chdir('/home/liuxfs/usage-monitor')
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'

from eink_dashboard import EinkDashboard

eink = EinkDashboard()
eink.init_hardware()

test_state = {
    "balance": {"total": "16.58", "currency": "CNY", "is_available": True},
    "usage": {
        "period_spending": "3.42",
        "total_spending": "127.80",
        "total_requests": 1547,
        "total_tokens": 2450000,
        "models": [
            {"name": "deepseek-chat", "tokens": 1500000, "requests": 1200},
            {"name": "deepseek-reasoner", "tokens": 950000, "requests": 347},
        ]
    },
    "cc_status": "idle",
    "cc_context_percent": 35,
    "cc_round": 12,
    "last_updated": {"balance": 0, "usage": 0},
    "network_latency_ms": 23,
    "services": {"deepseek_api": "up", "deepseek_platform": "up"},
}

result = eink.render(test_state)
print(f"Render result: {result}")
eink.sleep()
print("Dashboard rendered!")
