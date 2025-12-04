using System;
using System.Collections.Generic;
using UnityEngine;
using LegoVR.Mapping;   // GridMapper
using LegoVR.Network;   // NetworkManager, PayloadRoot (형 선언은 풀네임으로 씀)

namespace LegoVR.Managers
{
    /// <summary>
    /// 네트워크에서 JSON payload를 받아서
    /// 레고 건물(빌딩)들을 격자 좌표에 맞게 배치하는 매니저.
    /// </summary>
    public class GameStateManager : MonoBehaviour
    {
        [Serializable]
        public class BuildingMapping
        {
            [Tooltip("payload label (예: Building_02)")]
            public string label;

            [Tooltip("Hierarchy에 있는 실제 GameObject (예: Building_02)")]
            public GameObject target;

            [Tooltip("이 빌딩 프리팹의 Y축 회전 보정 값 (deg)\n예: 기본이 옆을 보고 있으면 90, 180 등")]
            public float rotationOffsetY = 0f;
        }

        [Header("References")]
        public GridMapper gridMapper;
        public NetworkManager networkManager;

        [Header("Building Mappings")]
        public List<BuildingMapping> buildingMappings = new List<BuildingMapping>();

        // 🔥 이제 label → BuildingMapping 으로 저장 (기존: GameObject만 저장)
        private readonly Dictionary<string, BuildingMapping> _buildingDict =
            new Dictionary<string, BuildingMapping>();

        private void Awake()
        {
            BuildBuildingDictionary();

            if (networkManager != null)
            {
                // ★ 문자열(JSON) 단위로 받는 이벤트에 구독
                networkManager.OnMessageReceived += HandlePayloadJson;
            }
            else
            {
                Debug.LogWarning("[GameState] NetworkManager reference not set.");
            }
        }

        private void OnDestroy()
        {
            if (networkManager != null)
            {
                networkManager.OnMessageReceived -= HandlePayloadJson;
            }
        }

        /// <summary>
        /// Inspector에서 설정한 BuildingMappings를 Dictionary로 변환.
        /// </summary>
        private void BuildBuildingDictionary()
        {
            _buildingDict.Clear();

            foreach (var mapping in buildingMappings)
            {
                if (mapping == null || mapping.target == null || string.IsNullOrEmpty(mapping.label))
                    continue;

                if (_buildingDict.ContainsKey(mapping.label))
                {
                    Debug.LogWarning($"[GameState] Duplicate building label: {mapping.label}");
                    continue;
                }

                _buildingDict[mapping.label] = mapping;
            }

            Debug.Log($"[GameState] Building mappings initialized. count={_buildingDict.Count}");
        }

        // ======================================================
        //  1) JSON 문자열을 받으면 여기서 파싱
        // ======================================================
        private void HandlePayloadJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
                return;

            LegoVR.Network.PayloadRoot root;
            try
            {
                // ★ 여기서도 네임스페이스를 풀네임으로 명시
                root = JsonUtility.FromJson<LegoVR.Network.PayloadRoot>(json);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[GameState] Failed to parse JSON: {e.Message}\n{json}");
                return;
            }

            if (root == null || root.objects == null)
                return;

            foreach (var obj in root.objects)
            {
                if (obj == null) continue;

                switch (obj.kind)
                {
                    case "building":
                        ApplyBuilding(obj);   // 아래 메서드
                        break;

                    // 나중에 character 같은 다른 kind 도 여기서 처리
                    default:
                        break;
                }
            }
        }

        // ======================================================
        //  2) 단일 building payload 적용
        // ======================================================
        private void ApplyBuilding(LegoVR.Network.ObjectPayload obj)
        {
            if (gridMapper == null)
            {
                Debug.LogWarning("[GameState] GridMapper is not assigned.");
                return;
            }

            if (!_buildingDict.TryGetValue(obj.label, out BuildingMapping mapping))
            {
                Debug.LogWarning($"[GameState] No building mapping for label: {obj.label}");
                return;
            }

            GameObject go = mapping.target;
            if (go == null)
            {
                Debug.LogWarning($"[GameState] Mapping target is null for label: {obj.label}");
                return;
            }

            // Python에서 넘어온 격자 좌표 (spawn_unity.x, y)
            int gridX = Mathf.RoundToInt(obj.spawn_unity.x);
            int gridY = Mathf.RoundToInt(obj.spawn_unity.y);

            // Grid → World 좌표 변환
            Vector3 pos = gridMapper.GridToWorld(gridX, gridY, 0f);

            // 🔥 회전 보정 적용
            float baseYaw = -obj.yaw_deg;             // Python 쪽 yaw (0/90/180/270)
            float offsetYaw = mapping.rotationOffsetY; // 프리팹별 보정값 (Inspector에서 설정)
            float finalYaw = baseYaw + offsetYaw;

            Debug.Log($"[GameState] {obj.label} -> grid=({gridX},{gridY}), world={pos}, yaw={baseYaw} + offset={offsetYaw} => {finalYaw}");

            // 위치 & 회전 적용
            go.transform.position = pos;
            go.transform.rotation = Quaternion.Euler(0f, finalYaw, 0f);
        }
    }
}
