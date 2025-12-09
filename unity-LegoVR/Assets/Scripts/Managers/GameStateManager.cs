using System;
using System.Collections.Generic;
using UnityEngine;
using LegoVR.Mapping;
using LegoVR.Network;

namespace LegoVR.Managers
{
    public class GameStateManager : MonoBehaviour
    {
        // =====================================================================
        //  BUILDING MAPPING
        // =====================================================================
        [Serializable]
        public class BuildingMapping
        {
            public string label;          // 예: "Building_01"
            public GameObject target;     // 건물 프리팹 인스턴스
            public float rotationOffsetY; // 프리팹 회전 보정값
        }

        // =====================================================================
        //  REFERENCES
        // =====================================================================
        [Header("References")]
        public GridMapper gridMapper;
        public NetworkManager networkManager;

        [Header("Building Mappings")]
        public List<BuildingMapping> buildingMappings = new List<BuildingMapping>();

        // label → mapping 정보
        private readonly Dictionary<string, BuildingMapping> _buildingDict =
            new Dictionary<string, BuildingMapping>();

        // =====================================================================
        //  RANDOM CHARACTERS
        // =====================================================================
        [Header("Random Characters")]
        [Tooltip("씬에 있는 랜덤 스폰 대상 캐릭터들")]
        public List<GameObject> randomCharacters = new List<GameObject>();

        [Tooltip("장애물(겹치면 안 되는 오브젝트)에 해당하는 LayerMask")]
        public LayerMask obstacleLayers;

        [Tooltip("랜덤 캐릭터가 차지하는 물리 반경(m)")]
        public float randomCharRadius = 0.6f;

        [Tooltip("랜덤 스폰 위치 탐색 최대 시도 횟수")]
        public int maxAttempts = 200;

        // =====================================================================
        //  UNITY EVENTS
        // =====================================================================
        private void Awake()
        {
            BuildBuildingDictionary();

            if (networkManager != null)
            {
                networkManager.OnMessageReceived += HandlePayloadJson;
            }
        }

        private void OnDestroy()
        {
            if (networkManager != null)
            {
                networkManager.OnMessageReceived -= HandlePayloadJson;
            }
        }

        // =====================================================================
        //  BUILD MAPPING DICTIONARY
        // =====================================================================
        private void BuildBuildingDictionary()
        {
            _buildingDict.Clear();

            foreach (var m in buildingMappings)
            {
                if (m == null || m.target == null || string.IsNullOrEmpty(m.label))
                    continue;

                if (_buildingDict.ContainsKey(m.label))
                {
                    Debug.LogWarning($"[GameState] Duplicate label: {m.label}");
                    continue;
                }

                _buildingDict[m.label] = m;
            }

            Debug.Log($"[GameState] Building mappings initialized. count={_buildingDict.Count}");
        }

        // =====================================================================
        //  PAYLOAD 처리
        // =====================================================================
        private void HandlePayloadJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
                return;

            PayloadRoot root;
            try
            {
                root = JsonUtility.FromJson<PayloadRoot>(json);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[GameState] JSON parse error: {e.Message} \n {json}");
                return;
            }

            if (root == null || root.objects == null)
                return;

            foreach (var obj in root.objects)
            {
                if (obj == null)
                    continue;

                if (obj.kind == "building")
                {
                    ApplyBuilding(obj);
                }
                else if (obj.kind == "character")
                {
                    // character payload는 무시하고, 랜덤 스폰만 사용
                }
            }

            // 모든 payload 빌딩 적용이 완료되면 랜덤 캐릭터 스폰
            SpawnRandomCharacters();
        }

        // =====================================================================
        //  BUILDING 배치
        // =====================================================================
        private void ApplyBuilding(ObjectPayload obj)
        {
            if (!_buildingDict.TryGetValue(obj.label, out BuildingMapping mapping))
            {
                Debug.LogWarning($"[GameState] No building mapping for label: {obj.label}");
                return;
            }

            GameObject go = mapping.target;
            if (go == null)
            {
                Debug.LogWarning($"[GameState] Mapping target null for label: {obj.label}");
                return;
            }

            int gx = Mathf.RoundToInt(obj.spawn_unity.x);
            int gy = Mathf.RoundToInt(obj.spawn_unity.y);

            Vector3 worldPos = gridMapper.GridToWorld(gx, gy, 0f);

            float finalYaw = obj.yaw_deg + mapping.rotationOffsetY;

            go.transform.position = worldPos;
            go.transform.rotation = Quaternion.Euler(0f, finalYaw, 0f);

            Debug.Log($"[GameState] Placed {obj.label} at grid({gx},{gy}) worldPos={worldPos}");
        }

        // =====================================================================
        //  RANDOM CHARACTER SPAWN SYSTEM (Physics 기반)
        // =====================================================================

        private void SpawnRandomCharacters()
        {
            if (randomCharacters == null || randomCharacters.Count == 0)
                return;

            Debug.Log("[GameState] Random character spawn start.");

            foreach (var ch in randomCharacters)
            {
                if (ch == null)
                    continue;

                bool success = false;

                for (int i = 0; i < maxAttempts; i++)
                {
                    if (!TryGetRandomPointOnFloor(out Vector3 pos))
                        break;

                    if (!IsPositionFree(pos, randomCharRadius))
                        continue;

                    // 스폰 성공
                    ch.transform.position = pos;
                    ch.transform.rotation = Quaternion.Euler(0f, UnityEngine.Random.Range(0f, 360f), 0f);

                    Debug.Log($"[GameState] Character '{ch.name}' spawned at {pos}");
                    success = true;
                    break;
                }

                if (!success)
                {
                    Debug.LogWarning($"[GameState] No free position found for {ch.name}");
                }
            }
        }

        // =====================================================================
        //  FLOOR 랜덤 좌표 생성
        // =====================================================================
        private bool TryGetRandomPointOnFloor(out Vector3 pos)
        {
            pos = Vector3.zero;

            if (gridMapper == null || gridMapper.floor == null)
                return false;

            var renderer = gridMapper.floor.GetComponentInChildren<Renderer>();
            if (renderer == null)
                return false;

            Bounds b = renderer.bounds;

            float x = UnityEngine.Random.Range(b.min.x, b.max.x);
            float z = UnityEngine.Random.Range(b.min.z, b.max.z);
            float y = b.max.y + 0.1f; // 바닥 위 살짝 띄워두기

            pos = new Vector3(x, y, z);
            return true;
        }

        // =====================================================================
        //  위치가 장애물과 겹치는지 검사
        // =====================================================================
        private bool IsPositionFree(Vector3 pos, float radius)
        {
            Vector3 center = pos + Vector3.up * radius; // 바닥 콜라이더 피하기

            var hits = Physics.OverlapSphere(
                center,
                radius,
                obstacleLayers,
                QueryTriggerInteraction.Ignore
            );

            return hits == null || hits.Length == 0;
        }
    }
}
