"""
배포된 Streamlit 앱 URL로 논문/포스터용 QR 코드 PNG를 생성하는 선택적 도구.

이 스크립트는 앱 실행에는 필요 없으며(requirements.txt에 포함하지 않음),
배포 URL이 확정된 뒤 논문 제출용 자료를 만들 때만 로컬에서 1회 실행한다.

사용법:
    python -m pip install "qrcode[pil]"
    python scripts/generate_qr_code.py https://<app-name>.streamlit.app --out docs/qr_code.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import qrcode
except ImportError as exc:
    raise ImportError(
        "이 스크립트는 'qrcode' 패키지가 필요합니다. "
        "python -m pip install \"qrcode[pil]\" 로 설치한 뒤 다시 실행하세요."
    ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="배포 URL로 QR 코드 PNG 생성")
    parser.add_argument("url", help="배포된 Streamlit 앱의 실제 URL")
    parser.add_argument("--out", default="docs/qr_code.png", help="출력 PNG 경로")
    args = parser.parse_args()

    img = qrcode.make(args.url)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    print(f"QR code saved: {out_path} (encodes: {args.url})")


if __name__ == "__main__":
    main()
