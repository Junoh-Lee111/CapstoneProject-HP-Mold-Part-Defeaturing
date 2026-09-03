# Mold-Part Defeaturing

우송대학교 SW중심대학사업 2026-2학기 캡스톤디자인(창의종합설계) 프로젝트 — HP2 팀

## 프로젝트 개요

AI 기반 금형/부품 CAD 형상 단순화(defeaturing) 자동화 기술 개발.

- **Input**: Mold/Part CAD 파일 (.STEP)
- **Output**: CAE 해석에 적합하도록 단순화된 CAD 모델 (.STEP 우선, NX 2순위)
- **핵심 작업**: hole, fillet, chamfer, rib, boss, emboss 등 형상 피처 인식 → 해석 정확도에 대한 영향을 최소화하면서 불필요한 피처 제거

### Objectives
- CAE 지오메트리 전처리 자동화
- 피처 중요도 판단 및 제거 결정 학습
- 수작업 개입 최소화

### Required Domain Knowledge
- 형상 피처 인식 (hole, fillet, chamfer, rib, boss)
- 3D 형상 분류 / ML·딥러닝
- Defeaturing 규칙 및 학습 데이터 구축

### Output
- 시뮬레이션 대응 가능한 단순화 CAD (.STEP)
- 원본 vs 단순화 비교 리포트
- 입력 포맷: STEP(1순위), NX(2순위)

### Expected Value
- CAD 전처리 시간 70~90% 절감
- 대량 시뮬레이션 자동화 기반 마련
- HP Printing 제품 개발 시뮬레이션 효율 향상

## 팀 정보

| 구분 | 내용 |
|---|---|
| 참여기업 | HP Printing Korea |
| 멘토 | Byoungho Yoo (CAE) |
| 담당교수 | Edward Youngil Kim (ed.kim@wsu.ac.kr) |
| 팀원 | Vangala Hemanth Reddy, Tahir Aneela, 이준오(202010128), Balcha Kidus Elias |

## 수업 일정 (2026 Fall, 9/3 ~ 12/17, 매주 목 13:00~18:00)

| 주차 | 일자 | 내용 |
|---|---|---|
| W1 | 9/3 | 수업/프로젝트 소개, 팀 빌딩 |
| W2 | 9/10 | 프로젝트 조사 및 제안서 작성 |
| W3 | 9/17 | 시스템 아키텍처 다이어그램, 요구사항 분석(FR/NFR) |
| W4 | 10/1 | 프로젝트 제안서 발표, HLD 작성 시작 |
| W5 | 10/8 | HLD 작성 (모듈 다이어그램) |
| W6 | 10/15 | HLD 제출, LLD 상세설계 시작 |
| W7 | 10/22 | HLD 리뷰, LLD 작성/제출, 진행 발표자료 |
| W8 | 10/29 | 기업 멘토 대상 진행상황 발표 (HPPK 방문) |
| W9 | 11/5 | 구현 Phase 1 (핵심 모듈/프로토타입) |
| W10 | 11/12 | - |
| W11 | 11/19 | 구현 Phase 2 (통합 테스트), 기능 개발 완료 선언 |
| W12 | 11/26 | - |
| W13 | 12/3 | 성능/정확도/병목 분석, 경진대회 패널 준비 |
| W14 | 12/10 | 완료보고 PPT 제출 |
| W15 | 12/17 | 최종 발표 및 시연 |

## 평가 기준
- 출석 20% / 태도(지각) 10% / 프로젝트 성과 70%
  - 제안서 발표 20%, 진행상황 발표 10%, 완료발표+최종보고서+Github/Notion 30%, 개인기여일지+동료평가 10%

## 폴더 구조

```
data/
  raw/          # 원본 CAD 파일 (.STEP 등)
  processed/    # 전처리/단순화된 CAD 파일
src/            # 소스 코드
notebooks/      # 실험/분석 노트북
models/         # 학습된 모델 가중치
docs/           # 제안서, 요구사항명세, HLD/LLD, 보고서 등
```
