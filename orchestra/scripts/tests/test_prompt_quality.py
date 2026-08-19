"""Prompt 质量回归：锁定证据、反证、不确定性和输出契约。"""
import json
import unittest
from pathlib import Path

import codex_modes


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = json.loads(
    (HERE / "prompt_quality_cases.json").read_text(encoding="utf-8")
)


class PromptQualityRegressionTest(unittest.TestCase):
    def assert_contract(self, text, contract):
        for needle in contract["must_contain"]:
            self.assertIn(needle, text)
        for needle in contract["must_not_contain"]:
            self.assertNotIn(needle, text)

    def test_codex_mode_prompts(self):
        prompts = {
            "mutual-review": codex_modes.build_prompt(
                "mutual-review", {"diff": "DIFF", "context": "CONTEXT"}
            ),
            "dual-implement": codex_modes.build_prompt(
                "dual-implement",
                {"spec": "SPEC", "impl_dir": "/tmp/impl", "tests_dir": "/tmp/tests"},
            ),
            "claim-check": codex_modes.build_prompt(
                "claim-check", {"claims": ["claim"]}
            ),
        }
        for name, prompt in prompts.items():
            with self.subTest(name=name):
                self.assert_contract(prompt, CASES["codex_modes"][name])

    def test_radar_rank_prompt(self):
        prompt = (ROOT / "templates" / "nightly-radar-rank.md").read_text(
            encoding="utf-8"
        )
        self.assert_contract(prompt, CASES["radar_rank"])


if __name__ == "__main__":
    unittest.main()
