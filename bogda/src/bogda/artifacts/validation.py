from pathlib import Path

from bogda.contracts import ArtifactRecord, ArtifactSpec


def validate_artifacts(
    attempt_dir: Path,
    specs: tuple[ArtifactSpec, ...],
) -> tuple[ArtifactRecord, ...]:
    records = []
    for spec in specs:
        path = attempt_dir / spec.path
        exists = path.exists()
        records.append(
            ArtifactRecord(
                uri=str(path.resolve()),
                kind=spec.kind,
                exists=exists,
                size_bytes=path.stat().st_size if exists and path.is_file() else None,
            )
        )
    return tuple(records)
