# SafeGuard TwinLab Agent — 배포 체크리스트

release/demo-ready 패키지를 실제로 공개 배포하기까지 남은 수동 단계를
순서대로 정리한다. 코드/문서 준비는 이미 완료되어 있으며, 아래는
GitHub/Streamlit Cloud/Zenodo 계정이 있어야 진행 가능한 단계다.

## 1) GitHub 저장소 생성 및 push

- [ ] 로컬 저장소 초기화: `git init`
- [ ] `.gitignore`가 `outputs/csv|figures|report`의 생성물, `__pycache__/`,
      `.pytest_cache/`를 제외하는지 확인 (이미 구성됨)
- [ ] 첫 커밋: `git add . && git commit -m "Initial commit: SafeGuard TwinLab Agent"`
- [x] GitHub 저장소 확정: https://github.com/yoontf0/safeguard-mmwave-simulator
- [ ] `git remote add origin https://github.com/yoontf0/safeguard-mmwave-simulator.git`
- [ ] `git push -u origin main` (아직 push 전이라면 최신 코드를 push할 것)

## 2) Streamlit Community Cloud 배포

- [ ] https://share.streamlit.io 접속 후 GitHub 계정 연동
- [ ] "New app" → repository/branch 선택, **Main file path**를
      `app/streamlit_app.py`로 지정
- [ ] Python version: `.python-version`(3.11)이 자동 인식되는지 확인,
      안 되면 Advanced settings에서 수동 지정
- [ ] `requirements.txt`가 저장소 루트에 있는지 확인 (이미 위치함, 자동 인식됨)
- [ ] 배포 후 최초 로딩 시 Demo Mode 4개 버튼과 Failure Scenario 버튼이
      정상 동작하는지, Paper-ready 자동 생성 버튼이 오류 없이 실행되는지
      직접 클릭해 확인
- [x] 배포된 앱 URL 확보: https://safeguard-mmwave-simulator.streamlit.app

## 3) README/문서에 실제 URL 반영

- [x] GitHub 저장소 URL(`yoontf0/safeguard-mmwave-simulator`)을 README.md,
      docs/index.md, CITATION.cff, PAPER_LINK_QR_KR.md, DEPLOYMENT_CHECKLIST.md
      전체에 반영 완료
- [x] Streamlit 배포 URL(`https://safeguard-mmwave-simulator.streamlit.app`)을
      `README.md`(Open in Streamlit 배지), `docs/index.md`(Live Demo 링크),
      `PAPER_LINK_QR_KR.md`(전체) 에 반영 완료
- [ ] `CITATION.cff`의 저자 정보(`<팀장 성>`, `<팀장 이름>`, `<소속 기관/학교>`)를
      실제 값으로 교체 (아직 placeholder 상태)

## 4) GitHub Pages 활성화

- [ ] GitHub 저장소 → Settings → Pages
- [ ] Source: `Deploy from a branch` 선택, Branch: `main` / `/docs` 선택
- [ ] 저장 후 수 분 내 `https://yoontf0.github.io/safeguard-mmwave-simulator/`에서
      `docs/index.md`가 렌더링되는지 확인
- [ ] `docs/sample_outputs/`의 표/그림/텍스트 링크가 정상적으로 열리는지 확인

## 5) Zenodo DOI 발급 준비

- [ ] https://zenodo.org 에 GitHub 계정으로 로그인
- [ ] Zenodo의 GitHub 연동 페이지에서 대상 저장소를 "On"으로 전환
- [ ] `CITATION.cff`의 저자/소속/키워드가 정확한지 최종 검토
- [ ] GitHub에서 새 **Release**(예: `v1.0.0`) 생성 및 publish
      → Zenodo가 자동으로 아카이브하고 DOI를 발급함
- [ ] 발급된 DOI를 `CITATION.cff`에 `doi:` 필드로 추가하고, README에도
      DOI 배지를 추가 (`https://zenodo.org/badge/DOI/<DOI>.svg`)

## 6) 배포 후 최종 점검

- [ ] `python -m pytest tests/ -v` — 로컬에서 51개 테스트 전체 통과 확인
- [ ] `python scripts/clean_outputs.py` 실행 후 `python scripts/generate_paper_outputs.py`로
      11개 파일이 정상 재생성되는지 확인 (재현성 검증)
- [ ] 배포된 Streamlit 앱에서 mmWave Sensor Profile(C4001 / TI) 양쪽 모두
      정상 동작하는지 확인
- [ ] 배포된 Streamlit 앱에서 hardware_log.csv 업로드(`sample_data/` 파일
      사용)가 정상 동작하는지 확인
- [ ] [DEMO_SCRIPT_KR.md](DEMO_SCRIPT_KR.md)로 실제 발표 리허설 1회 진행

## 참고: 로컬 실행이 가능한 항목 (이미 검증 완료)

아래 항목은 이 세션에서 이미 실행/검증되었으므로 배포 시 참고만 하면 된다.

- ✅ `requirements.txt`가 `app/streamlit_app.py` 실행에 필요한 패키지
  (streamlit, pandas, numpy, matplotlib)를 모두 포함함을 확인
- ✅ 하드코딩된 Windows 절대경로 없음 (전부 `pathlib` 기반 상대 경로)
- ✅ `.gitignore`, `.streamlit/config.toml`, `.python-version` 구성 완료
- ✅ `docs/index.md`, `docs/sample_outputs/`(paper-ready 산출물 12개) 준비 완료
- ✅ `CITATION.cff`, `LICENSE`(MIT) 준비 완료 (저자 placeholder만 교체 필요)
- ✅ pytest 51개 전체 통과, 대시보드 mmWave profile(C4001/TI) 양쪽 라이브 검증 완료
- ✅ GitHub 저장소 URL(`https://github.com/yoontf0/safeguard-mmwave-simulator`)과
  Streamlit 배포 URL(`https://safeguard-mmwave-simulator.streamlit.app`) 모두
  확정 및 전체 문서 반영 완료. 남은 것은 CITATION.cff 저자 정보와
  섹션 4~6(GitHub Pages 활성화, Zenodo DOI, 배포 앱 라이브 점검)뿐이다.
