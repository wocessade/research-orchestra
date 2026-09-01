"""Named values shared by the console.

Keep in lockstep with bogda.contracts.runner_packet and
bogda.budget.deepseek_balance. The RK3528 console venv does not mount
/opt/bogda/src, so these must not be imported from bogda at module load.
"""

PI_SERVICE_POOL = "pi-service"
RESEARCH_POOL = "dorm-x86"
DEFAULT_DEEPSEEK_API_BASE = "https://api.deepseek.com"
