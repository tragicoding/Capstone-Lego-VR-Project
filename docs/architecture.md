
Directory 구조

lego-vr-project/                     # ✅ Git 루트 (여기서 git init)
├── README.md                        # 전체 프로젝트 개요, 실행 방법
├── .gitignore                       # Python + Unity 공용 ignore
├── docs/                            # 기획/설계/문서
│   ├── architecture.md              # 전체 시스템 구조, 데이터 흐름
│   ├── interaction-design.md        # 캐릭터/건물 인터랙션 기획
│   ├── marker-placement.md          # 마커 배치 규칙
│   └── images/
│       └── system-diagram.png
│
├── vision-python/                   # 🟦 Python: 카메라 + ArUco + TCP
│   ├── README.md                    # Python 모듈 설명, 실행방법
│   ├── requirements.txt             # pip 패키지 목록
│   ├── environment.yml              # (선택) conda 환경 내보낸 것
│   ├── src/
│   │   ├── __init__.py              # 패키지 인식용 (비워둬도 됨)
│   │   ├── app/
│   │   │   └── main.py              # 엔트리포인트 (카메라→마커→TCP 송신)
│   │   │
│   │   ├── config/                  # 설정 계층 (기능별로 분리)
│   │   │   ├── __init__.py
│   │   │   ├── camera_config.py     # 카메라 인덱스, 해상도, FPS
│   │   │   ├── tcp_config.py        # TCP HOST, PORT, 전송 간격
│   │   │   ├── marker_config.py     # 마커 ID, 기준 마커, 오브젝트 매핑
│   │   │   └── path_config.py       # 로그/데이터 경로(필요시)
│   │   │
│   │   ├── vision/                  # OpenCV + ArUco 실제 처리
│   │   │   ├── __init__.py
│   │   │   ├── camera.py            # VideoCapture 열기, 프레임 읽기
│   │   │   ├── aruco_detector.py    # 마커 검출, ID/코너/센터 계산
│   │   │   └── calibration.py       # (옵션) 카메라 캘리브레이션
│   │   │
│   │   ├── mapping/                 # 좌표계 변환/그리드 매핑
│   │   │   ├── __init__.py
│   │   │   ├── homography.py        # 이미지 → 레고판 평면 좌표
│   │   │   ├── grid_mapping.py      # 평면 좌표 → LEGO gridX, gridY
│   │   │   └── object_mapping.py    # grid + markerID → Unity에 보낼 오브젝트 리스트
│   │   │
│   │   ├── network/                 # TCP 통신 계층
│   │   │   ├── __init__.py
│   │   │   ├── tcp_server.py        # TCP 서버 생성, 연결 accept, 송신 함수
│   │   │   └── protocol.py          # Unity용 JSON 포맷 직렬화/역직렬화
│   │   │
│   │   ├── models/                  # 데이터 모델 (Pydantic 등)
│   │   │   ├── __init__.py
│   │   │   └── dto.py               # Marker, ObjectData, FramePayload 등 구조체
│   │   │
│   │   └── utils/                   # 공용 유틸
│   │       ├── __init__.py
│   │       ├── logging_utils.py     # 로그 포맷, 디버그 출력
│   │       └── timing.py            # FPS, 처리 시간 측정
│   │
│   └── tests/                       # 🧪 Python 단위 테스트/통합 테스트
│       ├── __init__.py              # (있으면 패키지 인식, 없어도 pytest는 돌아감)
│       ├── test_aruco_on_image.py   # 샘플 이미지에서 마커 검출 테스트
│       ├── test_mapping.py          # homography/grid/object 매핑 로직 테스트
│       └── test_tcp_connection.py   # TCP 서버/클라이언트 통신 테스트
│
└── unity-LegoVR/                    # 🟩 Unity VR 프로젝트
    ├── Assets/
    │   ├── Scenes/
    │   │   └── MainScene.unity
    │   │
    │   ├── Scripts/
    │   │   ├── Network/             # Python ↔ Unity 통신 관련
    │   │   │   └── MarkerReceiver.cs        # TCP 클라이언트 + JSON 수신
    │   │   │
    │   │   ├── Mapping/             # 마커/그리드 → Unity 좌표
    │   │   │   ├── GridToWorldMapper.cs     # gridX,gridY → 월드 좌표
    │   │   │   └── MarkerObjectRegistry.cs  # markerID ↔ Prefab/타입 매핑
    │   │   │
    │   │   ├── Managers/            # 씬/게임 흐름 전체 관리
    │   │   │   ├── GameManager.cs           # 초기화, 오브젝트 스폰 관리
    │   │   │   └── InteractionManager.cs    # 상호작용 이벤트 중앙 관리
    │   │   │
    │   │   ├── Buildings/           # 건물 관련 로직
    │   │   │   ├── BuildingController.cs         # 공통 동작(하이라이트, 반응 등)
    │   │   │   ├── BuildingInteractionHandler.cs # 캐릭터/플레이어와 상호작용
    │   │   │   └── BuildingConfig.cs             # ScriptableObject, 설정값
    │   │   │
    │   │   ├── Characters/          # 캐릭터 관련 로직
    │   │   │   ├── CharacterController.cs        # 이동/애니메이션
    │   │   │   ├── CharacterInteraction.cs       # 건물, 트리거 반응
    │   │   │   └── CharacterState.cs             # Idle/Walk/Talk 등 상태 값
    │   │   │
    │   │   └── Interactions/        # 공통 인터랙션 컴포넌트
    │   │       ├── TriggerZone.cs            # 콜라이더 기반 트리거
    │   │       ├── ProximityEvent.cs         # 거리 기반 이벤트
    │   │       └── InteractionUI.cs          # 상호작용 UI 표시
    │   │
    │   ├── Prefabs/
    │   │   ├── Buildings/
    │   │   │   ├── Building_Low.prefab
    │   │   │   ├── Building_Mid.prefab
    │   │   │   └── Building_High.prefab
    │   │   ├── Characters/
    │   │   │   ├── Character_A.prefab
    │   │   │   └── Character_B.prefab
    │   │   └── Environment/
    │   │       ├── GroundPlane.prefab
    │   │       └── MarkerDebug.prefab        # 디버그용 마커 시각화 오브젝트
    │   │
    │   ├── Materials/
    │   ├── Models/                           # fbx/obj 캐릭터, 건물 모델
    │   ├── Animations/
    │   └── ScriptableObjects/
    │       ├── BuildingConfigs/
    │       └── InteractionConfigs/
    │
    ├── Packages/
    ├── ProjectSettings/
    └── UserSettings/
