from pathlib import Path

from bogda.contracts import ArtifactRecord, ArtifactSpec


def validate_artifacts(
    attempt_dir: Path,
    specs: tuple[ArtifactSpec, ...],
) -> tuple[ArtifactRecord, ...]:
    resolved_attempt_dir = attempt_dir.resolve()
    records = []
    for spec in specs:
        declared_path = Path(spec.path)
        path = (resolved_attempt_dir / declared_path).resolve()
        contained = bool(spec.path) and not declared_path.is_absolute()
        if contained:
            try:
                path.relative_to(resolved_attempt_dir)
            except ValueError:
                contained = False
        exists = contained and (
            path.is_file() if spec.kind == "file" else path.exists()
        )
        records.append(
            ArtifactRecord(
                uri=str(path),
                kind=spec.kind,
                exists=exists,
                size_bytes=path.stat().st_size if exists and path.is_file() else None,
            )
        )
    return tuple(records)
