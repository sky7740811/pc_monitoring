# PC Monitor — 행동 강령 (절대 잊지 말 것)

## 기본 규칙
- 대답은 항상 한국어
- 전문용어는 영어 또는 프랑스어로 표기
- 코드 주석은 짧게 프랑스어로
- CHANGELOG.csv에 모든 수정사항 기록

## 구현 규칙
1. 이벤트 로그에 "정상 작동 중"은 절대 출력하지 않음 (성공 이벤트 무시)
2. 모든 UI 텍스트는 한글로 작성 (영어/프랑스어 금지)
3. 사용자에게 파일 수정 전 항상 허락 구할 것
4. 제공 전 반드시 `python _final_test.py` 실행해서 통과 확인
5. git commit 전 `git status` + `git diff` 확인

## 데이터 규칙
- NDJSON은 `log/raw/` 폴더에 저장
- HTML 보고서는 `log/` 폴더에 저장
- 세션 종료 시 save_html() + generate_report() 둘 다 호출

## 아이콘 규칙
- 바로가기는 `launcher.exe` 타겟 (PC Monitor.bat 실행)
- 아이콘은 `pc-monitor.ico` 사용
