"""
断点续写状态管理器 — StateManager

支持段落/步骤级状态快照，自动检测未完成项目，手动/自动恢复双入口。
"""

import json
import os
from pathlib import Path
from typing import Optional

class StateManager:
    """管理论文写作的断点续写状态"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.state_file = self.project_dir / ".checkpoint" / "state.json"

    def save_checkpoint(self, state: dict) -> str:
        """保存当前状态快照"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state["_checkpoint_time"] = __import__("datetime").datetime.now().isoformat()
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return str(self.state_file)

    def load_checkpoint(self) -> Optional[dict]:
        """加载最近的状态快照"""
        if not self.state_file.exists():
            return None
        with open(self.state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def detect_unfinished(self, scan_dir: str) -> list:
        """扫描目录，发现未完成的论文项目"""
        unfinished = []
        base = Path(scan_dir)
        for checkpoint_dir in base.glob("**/.checkpoint"):
            state_file = checkpoint_dir / "state.json"
            if state_file.exists():
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state.get("current_stage") and state.get("current_stage") != "completed":
                    unfinished.append({
                        "project_dir": str(checkpoint_dir.parent),
                        "state": state
                    })
        return unfinished

    def get_resume_summary(self) -> Optional[str]:
        """生成恢复摘要"""
        state = self.load_checkpoint()
        if not state:
            return None
        return (
            f"论文: {state.get('paper_slug', 'unknown')}\n"
            f"当前阶段: {state.get('current_stage', 'unknown')}\n"
            f"已完成小节: {len(state.get('completed_sections', []))}\n"
            f"最后保存: {state.get('_checkpoint_time', 'unknown')}"
        )


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    if action == "detect":
        scan_dir = sys.argv[2] if len(sys.argv) > 2 else "."
        manager = StateManager(".")
        projects = manager.detect_unfinished(scan_dir)
        if projects:
            print(f"发现 {len(projects)} 个未完成项目:")
            for p in projects:
                print(f"  - {p['project_dir']}: {p['state'].get('current_stage', '?')}")
        else:
            print("未发现未完成项目")
