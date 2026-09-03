# STEP 처리 라이브러리 비교조사

> 목적: Mold-Part Defeaturing 프로젝트에서 (1) STEP 파일을 읽고/쓰고/조작하는 CAD 커널 레이어와
> (2) 형상 피처를 AI가 인식할 수 있는 표현(그래프 등)으로 바꾸는 레이어에 쓸 라이브러리를 선정하기 위한 조사.
> 조사일: 2026-09 (최신 릴리스 기준 변동 가능, 실제 도입 전 버전 재확인 필요)

## 1. 전체 그림

```
STEP 파일(.step)
   │  ① 읽기/파싱 (CAD 커널)
   ▼
B-rep 모델 (Face/Edge/Vertex 위상 구조)
   │  ② 그래프 표현 변환 (ML용 wrapper)
   ▼
Face adjacency graph + UV 샘플링 등
   │  ③ 피처 인식 모델 (GNN 등)
   ▼
"이 face/edge는 hole/fillet/chamfer/rib/boss 이다" 라벨
   │  ④ 제거 로직 (다시 CAD 커널로)
   ▼
단순화된 STEP 파일 출력
```

①④는 **CAD 커널 라이브러리**, ②는 **ML 연결용 wrapper**, ③은 **피처 인식 모델(우리가 학습/구현)** 영역이다.

## 2. CAD 커널 라이브러리 비교 (①④ 담당)

모두 내부적으로 **Open CASCADE Technology (OCCT)** — C++로 작성된 오픈소스 3D CAD 커널 — 를 기반으로 한다. 즉 "어느 걸 고를지"는 "OCCT를 얼마나 raw하게 다룰지 vs. 편하게 감싸서 쓸지"의 문제에 가깝다.

| 라이브러리 | 성격 | STEP 지원 | 장점 | 단점 | 추천 용도 |
|---|---|---|---|---|---|
| **pythonocc-core** | OCCT의 거의 전체 C++ API(수천 개 클래스)를 파이썬으로 1:1 바인딩 | IGES/STEP/STL/PLY/OBJ/GLTF 등 폭넓은 데이터 교환 지원 | 가장 low-level, face/edge/vertex 단위까지 직접 제어 가능 → 피처 인식·제거 로직 구현에 필수적인 세밀한 접근 가능 | API가 C++ 스타일 그대로라 러닝커브 있음, 문서가 빈약한 편 | **핵심 STEP I/O 및 피처 조작 레이어** |
| **build123d** | CadQuery에서 파생되어 독립한 최신 파이썬 CAD 프레임워크. OCP(OCCT의 또 다른 파이썬 바인딩)를 기반 | STEP 등 주요 포맷 export/import | 문법이 파이썬스럽고 깔끔, 형상 조작 API가 정돈되어 있음, OCP의 저수준 타입에도 접근 가능 | 파라메트릭 "모델링"(설계)에 초점 → 기존 모델을 "분석/분해"하는 우리 용도로는 다소 무거울 수 있음 | 필요시 결과 검증/시각화용 보조 |
| **CadQuery** | build123d의 전신, 파라메트릭 CAD 스크립팅에 특화 | STEP, STL, AMF, 3MF 등 export | 직관적 API, 초보자 친화적 | build123d 대비 저수준(OCP raw type) 접근이 제한적 | 사용 우선순위 낮음 (build123d로 대체 가능) |
| **FreeCAD Python API** | FreeCAD(오픈소스 CAD 프로그램) 내장 파이썬 API, 역시 OCCT 기반 | STEP 읽기/쓰기 양호, GUI 병행 가능 | GUI로 결과를 눈으로 바로 확인 가능 (디버깅에 유용) | 무거운 애플리케이션 통째로 필요, 서버/배치 자동화에는 부적합 | 프로토타입 단계에서 결과 육안 검증용 |
| **Gmsh** | 메쉬 생성 전문 라이브러리 (OCCT geometry 연동 가능) | STEP import 후 메쉬 생성 | 실제 CAE 메쉬 품질 평가(우리 프로젝트의 "성공 기준" 검증)에 필요 | CAD 형상 편집 자체는 지원 X, 메쉬 생성 전용 | **평가 단계**(단순화 전후 메쉬 품질/해석 비교)에 활용 |

**결론**: 코어 레이어는 **pythonocc-core**로 간다. 이유:
- OCCT의 거의 모든 기능(face/edge 순회, 곡률 계산, boolean 연산, fillet/chamfer 제거 API 등)에 직접 접근 가능해야 "피처를 인식해서 제거"하는 이 프로젝트의 핵심 로직을 구현할 수 있음
- build123d/CadQuery는 "새 모델을 설계"하는 데 최적화되어 있어서, "기존 모델을 분석하고 일부만 제거"하는 우리 워크플로우에는 pythonocc-core가 더 적합
- 결과 시각화·검증 단계에서는 FreeCAD를 보조로 사용 가능

## 3. ML 연결용 wrapper (②)

| 라이브러리 | 설명 | 비고 |
|---|---|---|
| **occwl** | Autodesk AI Lab이 공개한 pythonocc 위의 경량 wrapper. B-rep → face adjacency graph 변환, face/edge의 UV 파라미터 도메인 샘플링을 지원 | UV-Net 등 여러 CAD 딥러닝 논문의 공식 구현체가 이 라이브러리를 사용. **B-rep을 그래프로 바꾸는 반복 작업을 직접 짤 필요가 없어짐** → 우리 프로젝트에서 채택 유력 |

## 4. 피처 인식 모델(③) — 참고할 기존 연구/구현체

직접 밑바닥부터 만들기보다 아래 공개 구현체를 참고/전이학습 하는 것을 권장:

| 이름 | 방식 | 비고 |
|---|---|---|
| **UV-Net** (Autodesk) | face의 UV grid를 CNN으로, face adjacency graph를 GNN으로 처리 후 결합 | occwl과 세트로 쓰기 좋음 |
| **BRepNet** (Autodesk) | B-rep의 coedge(방향 있는 edge) 기준으로 컨볼루션 커널 정의 → 중간 표현 변환 없이 B-rep에서 직접 학습 | topology-aware, 논문/구현체 공개 |
| **AAGNet** | Attributed Adjacency Graph(gAAG) 기반, 기하/위상/추가 속성을 모두 그래프에 반영해 machining feature 인식 | 비교적 최신, GitHub에 학습 코드+데이터 생성 도구 포함 → **우리 baseline 후보 1순위** |
| **BrepMFR** | Transformer + graph attention 기반 machining feature recognition, domain adaptation 지원 | 서로 다른 CAD 소스 간 일반화 성능 좋음 (HP 실데이터가 학습 데이터와 다를 때 유리) |

## 5. 학습/검증용 공개 데이터셋

우리 프로젝트는 HP 실제 CAD를 받기 전까지, 혹은 데이터 양이 부족할 때 아래로 사전학습/검증 가능:

| 데이터셋 | 규모 | 라벨 | 비고 |
|---|---|---|---|
| **MFCAD** | 15,488개 모델 | 16종 machining feature (chamfer, hole 등), 평면 face만 | 비교적 단순, 시작하기 좋음 |
| **MFCAD++** | 59,655개 모델 | 24종 feature, 곡면 포함, 모델당 3~10개 feature | MFCAD보다 현실적/어려움 |
| **Fusion 360 Gallery – Segmentation Dataset** | 35,858개 모델 (STEP 포맷 제공) | face별 8개 카테고리 (ExtrudeSide/End, CutSide/End, Fillet, Chamfer, RevolveSide/End) | Autodesk 공식 배포, STEP 원본 포함이라 pythonocc/occwl 파이프라인 검증에 바로 사용 가능 |

## 6. 종합 결론 (초기 기술 스택 제안)

```
STEP I/O + 형상 조작   →  pythonocc-core
B-rep → 그래프 변환    →  occwl
피처 인식 모델          →  AAGNet 또는 UV-Net 기반 커스텀 (MFCAD/MFCAD++ or Fusion360 Gallery로 사전학습 → HP 데이터로 파인튜닝)
단순화 전후 검증        →  Gmsh (메쉬 품질) + FreeCAD(육안 검증)
```

## 7. Open Questions
- [ ] pythonocc-core의 fillet/chamfer 자동 제거(defeaturing) API 실제 동작 검증 (`BRepFilletAPI`, `ShapeUpgrade` 등)
- [ ] occwl이 최신 pythonocc-core 버전과 호환되는지 확인 (설치 후 버전 고정)
- [ ] Fusion 360 Gallery STEP 데이터로 pythonocc-core 로딩 파이프라인 프로토타입 (W3 목표)
- [ ] HP로부터 실제 CAD 샘플 확보 일정 확인

## 참고 자료
- [Top Open Source CAD APIs and Libraries for Developers in 2026](https://blog.fileformat.com/cad/top-open-source-cad-api-and-libraries-for-developers-in-2026)
- [build123d GitHub](https://github.com/gumyr/build123d)
- [CadQuery Documentation](https://cadquery.readthedocs.io/en/latest/)
- [pythonocc-core GitHub](https://github.com/tpaviot/pythonocc-core)
- [AAGNet GitHub](https://github.com/whjdark/AAGNet)
- [Fusion 360 Gallery Dataset GitHub](https://github.com/AutodeskAILab/Fusion360GalleryDataset)
- [BRepGAT (JCDE)](https://academic.oup.com/jcde/article/10/6/2384/7453688)
- [FilletRec (arXiv)](https://arxiv.org/pdf/2511.05561)
