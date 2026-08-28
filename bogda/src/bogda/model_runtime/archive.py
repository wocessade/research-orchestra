from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from bogda.model_runtime.contracts import PromptArtifactV1, PromptArchivePort


class PromptArchiveConflictError(RuntimeError):
    """Raised when an archive target already contains different content."""

    def __init__(self) -> None:
        super().__init__("prompt archive target contains different content")


class FilePromptArchive(PromptArchivePort):
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def archive(self, run_id: str, call_id: str, prompt: str) -> PromptArtifactV1:
        self._validate_identifier(run_id)
        self._validate_identifier(call_id)
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")

        content = prompt.encode("utf-8")
        digest = sha256(content).hexdigest()
        path = self._root / run_id / f"{call_id}.prompt.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            if sha256(path.read_bytes()).hexdigest() != digest:
                raise PromptArchiveConflictError() from None

        return PromptArtifactV1(path=str(path), sha256=digest)

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in {".", ".."}
            or "/" in identifier
            or "\\" in identifier
        ):
            raise ValueError("archive identifiers must be single path segments")


__all__ = ["FilePromptArchive", "PromptArchiveConflictError"]
