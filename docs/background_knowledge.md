# 배경지식 정리

> 목적: 이 프로젝트(Mold-Part Defeaturing)를 이해하고 개발하는 데 필요한 지식을 영역별로 정리.
> 우선순위: ★★★(당장 필요) → ★(나중에 필요/있으면 좋음)

## 1. CAD 기초 개념 ★★★

이 프로젝트의 대상 자체를 이해하려면 필수.

- **B-rep (Boundary Representation)**: 3D 형상을 면(Face)·모서리(Edge)·꼭짓점(Vertex)의 위상(topology) + 각 면/모서리의 기하(geometry, 곡률·곡면방정식 등)로 표현하는 방식. 우리가 다루는 모든 CAD 커널(OCCT)의 근본 데이터 구조.
- **STEP 포맷 (ISO 10303)**: CAD 소프트웨어 간 표준 교환 포맷. 텍스트 기반이며 내부적으로 B-rep 구조를 그대로 담고 있음. `.step`/`.stp` 확장자.
- **형상 피처(Feature) 용어**: 프로젝트에서 계속 등장하는 개념이라 반드시 구분할 수 있어야 함
  - **Hole**: 구멍 (관통/비관통)
  - **Fillet**: 모서리를 둥글게 깎은 부분
  - **Chamfer**: 모서리를 비스듬히 깎은 부분
  - **Rib**: 강도 보강용 얇은 판 형태 돌출부
  - **Boss**: 원통형 돌출 기둥 (주로 나사 체결용)
  - **Emboss**: 로고/글자 등 양각/음각
- **Defeaturing**: 해석에 불필요한 세부 형상을 제거해 모델을 단순화하는 작업. 왜 하는지(메쉬/해석 시간 단축) 이해 필요.
- **금형(Mold) 기초**: 사출성형 등에서 부품을 찍어내는 틀. 왜 부품 CAD와 별개로 "금형" CAD가 존재하는지 정도는 알아두면 좋음 (★).

**추천 학습 경로**: OCCT 공식 문서의 "Modeling Data" 개요, 또는 STEP 파일을 텍스트 에디터로 직접 열어서 구조를 눈으로 확인해보는 것부터 시작하면 빠르게 감이 옴.

## 2. CAE / 시뮬레이션 기초 ★★

"왜 defeaturing이 필요한가"의 답이 여기 있음 — 성공 기준(70~90% 시간 절감)을 판단하려면 최소한의 이해 필요.

- **CAE (Computer-Aided Engineering)**: 구조/유동/열 등 해석 시뮬레이션 전반을 지칭.
- **FEM (유한요소법) 개념**: 형상을 작은 요소(mesh)로 쪼개서 근사 계산하는 원리. 디테일이 많을수록 메쉬가 조밀해지고 계산량이 급증하는 이유를 이해해야 "왜 defeaturing이 전처리 시간을 줄여주는지" 설명 가능.
- **메쉬 품질(Mesh Quality)**: 단순화 전후 비교 시 사용할 지표 (요소 개수, 왜곡도 등). Gmsh로 실습 가능.
- 깊게 팔 필요는 없음 — "형상 디테일 ↔ 메쉬 크기 ↔ 계산 시간"의 관계만 명확히 이해하면 충분.

## 3. Python CAD 프로그래밍 ★★★

실제 구현에 바로 쓰이는 부분.

- **pythonocc-core 기본 사용법**: STEP 파일 읽기/쓰기, `TopoDS_Shape` 순회(면/모서리 iterate), 곡면 타입 조회, boolean 연산, fillet/chamfer 관련 API(`BRepFilletAPI` 등).
- **occwl**: pythonocc 위에서 B-rep → 그래프 변환을 도와주는 wrapper. API 자체는 얇아서 pythonocc 기본기만 있으면 빠르게 습득 가능.
- 필요 시 참고: FreeCAD Python API (결과 시각화용, 선택사항).

## 4. 3D 형상 인식 / 그래프 딥러닝 ★★★

피처 인식 모델을 이해·구현하려면 필요. AI/빅데이터 전공이면 기본 ML은 있을 테니, 아래는 "CAD 도메인에 특화된" 부분 위주로 채우면 됨.

- **그래프 신경망(GNN) 기초**: 노드(면)·엣지(면 간 인접관계)로 이루어진 그래프에서 정보를 전파(message passing)하는 원리. GCN/GAT 정도의 기본 개념.
- **B-rep을 그래프로 표현하는 방법**: face adjacency graph (면을 노드로, 인접한 면을 엣지로 연결), 여기에 UV 파라미터 샘플링으로 각 면의 기하 정보를 특징(feature)으로 부여하는 방식(UV-Net 접근).
- **Machining Feature Recognition 개념**: 기계가공/설계에서 "이 면 집합은 hole이다/fillet이다"를 분류하는 기존 연구 흐름. UV-Net, BRepNet, AAGNet, BrepMFR 등 최근 사용 논문 흐름을 파악해두면 모델 선택·구현 시 도움됨 ([step_library_comparison.md](step_library_comparison.md) 참고).
- **Domain Adaptation 개념** (★, 선택): 공개 데이터셋으로 학습한 모델을 HP의 실제 CAD 데이터에 적용할 때 성능 저하를 줄이는 기법. BrepMFR 검토 시 필요.

## 5. 소프트웨어 엔지니어링 프로세스 ★★★ (수업 요구사항)

수업 산출물 작성에 바로 필요.

- **요구사항 명세 (FR/NFR)**: 기능 요구사항(Functional Requirement) vs 비기능 요구사항(Non-Functional Requirement, 예: 처리 속도·정확도 목표) 구분해서 작성하는 법.
- **HLD (High-Level Design) / LLD (Low-Level Design)**: HLD는 모듈 단위 구조(지금 만든 architecture.md 수준), LLD는 각 모듈의 세부 로직(함수/클래스, 흐름도, 테스트 케이스 수준)까지 내려가는 설계. W6~W7에 필요.
- **Git 협업**: 브랜치 전략, PR 리뷰, 커밋 단위 관리 — 팀원들과 코드 합칠 때 필요.

## 6. 우선순위 요약

지금(제안서~아키텍처 단계) 당장 필요한 순서:

1. CAD 기초 개념(1) — 프로젝트를 설명/이해하는 데 필수, 가장 먼저
2. Python CAD 프로그래밍(3) — pythonocc-core로 STEP 파일 하나 열어서 면 개수 세보는 정도부터 실습 권장
3. 그래프 딥러닝 기초(4) — 모델 후보를 실제로 비교/구현하기 전에
4. CAE/시뮬레이션 기초(2) — 성공 기준 이해, 검증 단계 설계 시
5. 소프트웨어 프로세스(5) — HLD/LLD 작성 시점(W4~W7)에 맞춰

## 관련 문서
- [STEP 라이브러리 비교조사](step_library_comparison.md)
- [System Architecture (Draft)](architecture.md)
