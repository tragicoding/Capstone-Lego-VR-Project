using UnityEngine;

namespace LegoVR.Mapping
{
    /// <summary>
    /// 레고 격자 좌표(spawn_unity.x, y)를 Unity 월드 좌표로 바꾸는 매퍼.
    /// - Floor 메쉬의 bounds를 이용해서
    ///   "왼쪽 하단 블록의 중심"을 (1,1) 셀로 정의한다.
    /// - gridX, gridY 는 1 ~ gridWidth / gridHeight (1-based index) 라고 가정.
    /// </summary>
    public class GridMapper : MonoBehaviour
    {
        [Header("Floor Reference")]
        [Tooltip("레고 보드(바닥) 역할을 하는 Floor GameObject (씬 인스턴스)")]
        public Transform floor;     // Hierarchy의 Floor 인스턴스

        [Header("Grid Size (stud count)")]
        public int gridWidth = 64;
        public int gridHeight = 64;

        [Header("Height Offset")]
        [Tooltip("블록 위로 얼마나 띄울지 (필요하면 건물이 살짝 떠보이게)")]
        public float extraYOffset = 0f;

        [Header("Debug")]
        [Tooltip("씬에서 (1,1) 위치와 격자 윤곽을 Gizmo로 그릴지 여부")]
        public bool debugDraw = true;

        // 내부 계산 값
        private Renderer _floorRenderer;
        private float _cellSizeX = 1f;
        private float _cellSizeZ = 1f;

        // (1,1) 셀의 "중심" 월드 좌표
        private Vector3 _cell11Center;

        // Floor의 오른쪽 / 앞쪽 방향
        private Vector3 _rightDir;
        private Vector3 _forwardDir;

        private bool _initialized = false;

        private void Awake()
        {
            Initialize();
        }

        private void OnValidate()
        {
            if (!Application.isPlaying)
            {
                Initialize();
            }
        }

        /// <summary>
        /// Floor 메쉬 bounds를 이용해 cellSize와 (1,1) 셀 중심 좌표를 계산한다.
        /// </summary>
private void Initialize()
{
    _initialized = false;

    if (floor == null)
    {
        Debug.LogWarning("[GridMapper] Floor reference is not set.");
        return;
    }

    _floorRenderer = floor.GetComponentInChildren<Renderer>();
    if (_floorRenderer == null)
    {
        Debug.LogWarning("[GridMapper] Floor has no Renderer.");
        return;
    }

    var bounds = _floorRenderer.bounds;

    // 전체 월드 크기 → 칸 크기
    _cellSizeX = bounds.size.x / Mathf.Max(1, gridWidth);
    _cellSizeZ = bounds.size.z / Mathf.Max(1, gridHeight);

    // Floor의 로컬 오른쪽/앞쪽 방향
    _rightDir = floor.right.normalized;
    _forwardDir = floor.forward.normalized;

    // 🔥 Y는 바닥 '아래'가 아니라 '윗면' 기준으로 맞춰야 한다.
    float topY = bounds.max.y;

    // 왼쪽-아래-뒤 모서리의 X,Z + 윗면 Y
    Vector3 bottomLeftCorner = new Vector3(bounds.min.x, topY, bounds.min.z);

    _cell11Center =
        bottomLeftCorner
        + _rightDir * (_cellSizeX * 0.5f)
        + _forwardDir * (_cellSizeZ * 0.5f);

    _initialized = true;

    Debug.Log($"[GridMapper] Initialized. cellSizeX={_cellSizeX}, cellSizeZ={_cellSizeZ}");
    Debug.Log($"[GridMapper] (1,1) world pos = {_cell11Center}");
}


        /// <summary>
        /// 격자 좌표(1-based)를 Floor 기준 월드 좌표로 변환.
        /// gridX=1, gridY=1 → 왼쪽 하단 블록의 중심.
        /// </summary>
        public Vector3 GridToWorld(int gridX, int gridY, float height = 0f)
        {
            if (!_initialized)
            {
                Initialize();
                if (!_initialized)
                    return Vector3.zero;
            }

            int dx = gridX - 1;
            int dz = gridY - 1;

            Vector3 pos =
                _cell11Center
                + _rightDir * (_cellSizeX * dx)
                + _forwardDir * (_cellSizeZ * dz);

            pos += Vector3.up * (height + extraYOffset);
            return pos;
        }

#if UNITY_EDITOR
        // 씬에서 GridMapper 오브젝트를 선택했을 때 디버그 그리기
        private void OnDrawGizmosSelected()
        {
            if (!debugDraw)
                return;

            if (floor == null)
                return;

            if (_floorRenderer == null)
                _floorRenderer = floor.GetComponentInChildren<Renderer>();

            if (_floorRenderer == null)
                return;

            if (!_initialized)
                Initialize();
            if (!_initialized)
                return;

            var bounds = _floorRenderer.bounds;

            // (1,1) 셀 중심
            Gizmos.color = Color.green;
            Gizmos.DrawSphere(_cell11Center, 0.3f);

            // 전체 윤곽선
            Vector3 bl = new Vector3(bounds.min.x, _cell11Center.y, bounds.min.z); // bottom-left
            Vector3 br = bl + _rightDir * bounds.size.x;                           // bottom-right
            Vector3 tl = bl + _forwardDir * bounds.size.z;                         // top-left
            Vector3 tr = tl + _rightDir * bounds.size.x;                           // top-right

            Gizmos.color = Color.yellow;
            Gizmos.DrawLine(bl, br);
            Gizmos.DrawLine(br, tr);
            Gizmos.DrawLine(tr, tl);
            Gizmos.DrawLine(tl, bl);
        }
#endif
    }
}
