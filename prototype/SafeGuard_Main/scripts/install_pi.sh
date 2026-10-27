#!/usr/bin/env bash
set -euo pipefail

camera=0
for option in "$@"; do
  case "$option" in
    --camera) camera=1 ;;
    -h|--help)
      printf '%s\n' '사용: bash scripts/install_pi.sh [--camera]' \
        '기본: g++, CMake, JSON 헤더, pySerial 설치' \
        '--camera: Picamera2, OpenCV, NumPy도 설치'
      exit 0 ;;
    *) printf '알 수 없는 옵션: %s\n' "$option" >&2; exit 2 ;;
  esac
done

if ! command -v apt-get >/dev/null 2>&1; then
  printf '%s\n' 'Raspberry Pi OS / Debian 계열에서 실행하세요.' >&2
  exit 1
fi
privilege=()
if (( EUID != 0 )); then
  if ! command -v sudo >/dev/null 2>&1; then
    printf '%s\n' '패키지를 설치할 sudo 권한이 필요합니다.' >&2
    exit 1
  fi
  privilege=(sudo)
fi
packages=(g++ cmake nlohmann-json3-dev python3-serial)
if (( camera )); then
  packages+=(python3-picamera2 python3-opencv python3-numpy)
fi
"${privilege[@]}" apt-get update
"${privilege[@]}" apt-get install -y "${packages[@]}"
printf '%s\n' '설치 완료. 다음 명령: bash scripts/build.sh'

