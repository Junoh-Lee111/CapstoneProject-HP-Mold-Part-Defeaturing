# 프로젝트 제안서 (초안) — Mold-Part Defeaturing

> 2026 캡스톤디자인(창의종합설계) · Week 2 (9/10) 과제
> 참여기업: HP Printing Korea | 멘토: Byoungho Yoo (CAE) | 담당교수: Edward Youngil Kim

## 1. 과제 개요

**과제명**: AI 기반 금형/부품 CAD 형상 단순화(Mold-Part Defeaturing) 자동화

CAE(Computer-Aided Engineering) 해석을 수행하기 전, 실제 제품 설계에는 존재하지만 구조/유동 해석 결과에 큰 영향을 주지 않는 세부 형상(hole, fillet, chamfer, rib, boss, emboss 등)이 다수 포함되어 있다. 이러한 세부 형상은 메쉬 생성 시간과 해석 시간을 크게 늘리는 반면, 해석 정확도에 대한 기여는 낮다. 본 프로젝트는 이러한 불필요한 형상을 AI가 자동으로 인식하고 제거하여, CAE 해석에 바로 사용할 수 있는 단순화된 CAD 모델을 생성하는 자동화 기술을 개발한다.

## 2. 배경 및 문제 정의 (Why)

- CAE 엔지니어가 해석 전 CAD 모델의 불필요한 형상을 수작업으로 제거(defeaturing)하는 데 상당한 시간이 소요됨
- 수작업 defeaturing은 엔지니어의 경험에 의존하며, 일관성이 떨어지고 대량의 부품에 대해 확장하기 어려움
- HP Printing의 대량 시뮬레이션/제품 개발 프로세스에서 CAD 전처리가 병목으로 작용

## 3. 목표 (Objectives)

1. CAE 지오메트리 전처리 자동화
2. 형상 피처(hole, fillet, chamfer, rib, boss, emboss)의 중요도를 학습하여 제거 여부를 판단
3. 수작업 개입 최소화

## 4. Scope (MVP 기준)

- **Input**: Mold/Part CAD 파일 (.STEP 우선순위 1, NX 우선순위 2)
- **Output**:
  - 시뮬레이션 대응 가능한 단순화 CAD 모델 (.STEP)
  - 원본 vs 단순화 형상 비교 리포트
- 정확도와 해석 결과에 미치는 영향 최소화를 최우선 목표로 하며, 지원 형상 종류를 넓히는 것보다 핵심 피처(hole/fillet/chamfer/rib/boss)에 대한 정확도를 우선한다.

### Stretch Goals (MVP 이후, 논의 필요)
- emboss 등 추가 피처 유형 지원 확대
- NX 포맷 직접 지원
- 해석 결과(응력/변형 등) 기반 자동 검증 루프

## 5. 필요 도메인 지식

- 형상 피처 인식 (hole, fillet, chamfer, rib, boss)
- 3D 형상 분류 / ML·딥러닝 (예: point cloud, mesh, B-rep 기반 모델)
- CAD 파일 포맷(STEP) 파싱 및 조작 (예: OpenCASCADE, python-occ)
- Defeaturing 규칙 정의 및 학습 데이터 구축

## 6. 기대효과

- CAD 전처리 시간 70~90% 절감
- 대량 시뮬레이션 자동화 기반 마련
- HP Printing 제품 개발 시뮬레이션 효율 향상

## 7. 팀 구성 및 R&R (초안 — 논의 필요)

| 이름 | 역할 |
|---|---|
| Vangala Hemanth Reddy | TBD |
| Tahir Aneela | TBD |
| 이준오 | TBD |
| Balcha Kidus Elias | TBD |

## 8. 일정 (수업 일정 기준, [README.md](../README.md) 참고)

- W3 (9/17): 시스템 아키텍처 다이어그램, FR/NFR 작성
- W4 (10/1): 제안서 발표, HLD 착수
- W6 (10/15): HLD 제출
- W7 (10/22): LLD 제출
- W8 (10/29): 기업 멘토 대상 진행상황 발표
- W9~W11: 구현 (프로토타입 → 통합/테스트)
- W13 (12/3): 성능/정확도 분석
- W15 (12/17): 최종 발표 및 시연

## 9. 미결정 사항 / 다음 액션

- [x] STEP 파일 처리 라이브러리 선정 → [docs/step_library_comparison.md](step_library_comparison.md) 참고 (pythonocc-core + occwl 채택)
- [ ] 피처 인식에 사용할 3D 딥러닝 접근법 조사 (mesh-based vs. B-rep graph-based)
- [ ] HP로부터 샘플 CAD 데이터 확보 방안 확인
- [ ] 팀원별 R&R 확정
- [ ] 팀 그라운드룰 작성
