"""
SafeGuard TwinLab Agent - outputs/ 폴더 정리 스크립트.

outputs/csv, outputs/figures, outputs/report 안의 파일을 모두 삭제하고
빈 디렉터리 구조는 유지한다 (release 패키지를 깨끗한 상태로 되돌릴 때 사용).

사용법: python scripts/clean_outputs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import OUTPUTS_CSV_DIR, OUTPUTS_FIGURES_DIR, OUTPUTS_REPORT_DIR


def clean_dir(directory: Path) -> int:
    """디렉터리 내부의 파일만 삭제하고(.gitkeep 등 hidden 제외) 개수를 반환한다."""
    removed = 0
    for path in directory.glob("*"):
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()
            removed += 1
    return removed


def main() -> None:
    total = 0
    for directory in (OUTPUTS_CSV_DIR, OUTPUTS_FIGURES_DIR, OUTPUTS_REPORT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        n = clean_dir(directory)
        print(f"cleaned {directory}: {n}개 파일 삭제")
        total += n
    print(f"완료: 총 {total}개 파일 삭제")


if __name__ == "__main__":
    main()
