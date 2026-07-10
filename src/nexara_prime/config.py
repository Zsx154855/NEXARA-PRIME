from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    workspace_root: Path
    report_root: Path
    model_provider: str
    mock_model: bool
    api_host: str
    api_port: int

    @classmethod
    def from_env(cls, root: Path | None = None) -> "Settings":
        root = (root or Path.cwd()).resolve()
        db_path = Path(os.getenv("NEXARA_DB_PATH", str(root / "runtime" / "nexara.db"))).expanduser()
        workspace_root = Path(os.getenv("NEXARA_WORKSPACE_ROOT", str(root / "workspace"))).expanduser().resolve()
        report_root = Path(os.getenv("NEXARA_REPORT_ROOT", str(root / "reports"))).expanduser().resolve()
        return cls(
            db_path=db_path,
            workspace_root=workspace_root,
            report_root=report_root,
            model_provider=os.getenv("NEXARA_MODEL_PROVIDER", "mock"),
            mock_model=os.getenv("NEXARA_MOCK_MODEL", "true").lower() not in {"0", "false", "no"},
            api_host=os.getenv("NEXARA_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("NEXARA_API_PORT", "8765")),
        )

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.report_root.mkdir(parents=True, exist_ok=True)
