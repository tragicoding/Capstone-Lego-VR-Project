using System;
using System.Collections.Generic;
using UnityEngine;
using LegoVR.Mapping;   
using LegoVR.Network;   

namespace LegoVR.Managers
{
    public class GameStateManager : MonoBehaviour
    {
        // ================================================================
        //  Serializable Classes
        // ================================================================
        [Serializable]
        public class BuildingMapping
        {
            public string label;      // ex) "Building_01"
            public GameObject target; // hierarchy object
            public float rotationOffsetY = 0f;
        }

        [Serializable]
        public class RandomCharacterEntry
        {
            public GameObject prefab;
            public float radius = 0.8f;  // 차지하는 공간의 반경

            [HideInInspector] public GameObject instance;
        }

        // ================================================================
        //  Public Fields
        // ================================================================
        public GridMapper gridMapper;
        public NetworkManager networkManager;

        [Header("Building Mappings")]
        public List<BuildingMapping> buildingMappings = new List<BuildingMapping>();

        [Header("Random Characters (Spawn ONCE at Start)")]
        public List<RandomCharacterEntry> randomCharacters = new List<RandomCharacterEntry>();

        [Tooltip("랜덤 스폰 기준이 될 Floor Transform")]
        public Transform floor;            

        [Tooltip("랜덤 캐릭터 Y 높이 (바닥에서 얼마나 띄울지)")]
        public float randomHeight = 0.1f;

        [Tooltip("랜덤 위치 찾기 최대 시도 횟수")]
        public int maxAttempts = 200;

        [Header("XR Origin Character (1인칭)")]
        [Tooltip("씬에 있는 XR Origin (XR Rig) 오브젝트")]
        public GameObject xrOrigin;        

        // ================================================================
        //  Private Fields
        // ================================================================
        private Dictionary<string, BuildingMapping> _buildingDict =
            new Dictionary<string, BuildingMapping>();

        // 🔥 랜덤 캐릭터는 한 번만 스폰
        private bool _randomCharactersSpawned = false;

        // 🔥 XR Origin도 payload 기준으로 한 번만 위치 세팅
        private bool _xrOriginPlaced = false;

        // Floor bounds
        private float _minX, _maxX, _minZ, _maxZ;


        // ================================================================
        //  Unity Events
        // ================================================================
        private void Awake()
        {
            InitializeFloorBounds();
            BuildBuildingDictionary();

            if (networkManager != null)
                networkManager.OnMessageReceived += HandlePayloadJson;
            else
                Debug.LogWarning("[GameState] NetworkManager not assigned.");
        }

        private void OnDestroy()
        {
            if (networkManager != null)
                networkManager.OnMessageReceived -= HandlePayloadJson;
        }

        // ================================================================
        //  Initialize Floor Bounds
        // ================================================================
        private void InitializeFloorBounds()
        {
            if (floor == null)
            {
                Debug.LogError("[GameState] floor is not assigned.");
                return;
            }

            Renderer r = floor.GetComponentInChildren<Renderer>();
            if (r == null)
            {
                Debug.LogError("[GameState] floor has no Renderer.");
                return;
            }

            Bounds b = r.bounds;
            _minX = b.min.x;
            _maxX = b.max.x;
            _minZ = b.min.z;
            _maxZ = b.max.z;

            Debug.Log($"[GameState] Floor bounds initialized: X[{_minX} ~ {_maxX}], Z[{_minZ} ~ {_maxZ}]");
        }


        // ================================================================
        //  Build Building Dictionary
        // ================================================================
        private void BuildBuildingDictionary()
        {
            _buildingDict.Clear();

            foreach (var m in buildingMappings)
            {
                if (m == null || m.target == null || string.IsNullOrEmpty(m.label))
                    continue;

                _buildingDict[m.label] = m;
            }

            Debug.Log($"[GameState] Building mapping count = {_buildingDict.Count}");
        }

        // ================================================================
        //  Payload Handler
        // ================================================================
        private void HandlePayloadJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
                return;

            PayloadRoot root;
            try
            {
                root = JsonUtility.FromJson<PayloadRoot>(json);
            }
            catch (Exception)
            {
                Debug.LogWarning("[GameState] JSON parse error.");
                return;
            }

            if (root?.objects == null)
                return;

            foreach (var obj in root.objects)
            {
                if (obj.kind == "building")
                    ApplyBuilding(obj);

                if (obj.kind == "character")
                    TryApplyXROrigin(obj);
            }

            // 🔥 랜덤 캐릭터는 "딱 한 번만" 스폰한다
            if (!_randomCharactersSpawned)
            {
                SpawnRandomCharacters();
                _randomCharactersSpawned = true;
            }
        }

        // ================================================================
        //  Building Placement
        // ================================================================
        private void ApplyBuilding(ObjectPayload obj)
        {
            if (!_buildingDict.TryGetValue(obj.label, out var mapping))
            {
                Debug.LogWarning($"[GameState] No building mapping for label: {obj.label}");
                return;
            }

            GameObject go = mapping.target;

            int gx = Mathf.RoundToInt(obj.spawn_unity.x);
            int gy = Mathf.RoundToInt(obj.spawn_unity.y);
            Vector3 pos = gridMapper.GridToWorld(gx, gy, 0f);

            // 🔥 yaw 반전 적용
            float yaw = -(obj.yaw_deg + mapping.rotationOffsetY);

            go.transform.position = pos;
            go.transform.rotation = Quaternion.Euler(0f, yaw, 0f);

            Debug.Log($"[GameState] Building {obj.label} placed at {pos}, yaw={yaw}");
        }

        // ================================================================
        //  XR Origin (Character) Placement  — 한 번만!
        // ================================================================
        private void TryApplyXROrigin(ObjectPayload obj)
        {
            // 이미 한 번 자리를 잡았으면 더 이상 덮어쓰지 않음
            if (_xrOriginPlaced)
                return;

            if (xrOrigin == null)
            {
                Debug.LogWarning("[GameState] xrOrigin is not assigned.");
                return;
            }

            int gx = Mathf.RoundToInt(obj.spawn_unity.x);
            int gy = Mathf.RoundToInt(obj.spawn_unity.y);

            Vector3 pos = gridMapper.GridToWorld(gx, gy, 0f);
            float yaw = -obj.yaw_deg;   // 건물과 동일하게 부호 반전

            xrOrigin.transform.position = pos;
            xrOrigin.transform.rotation = Quaternion.Euler(0f, yaw, 0f);

            _xrOriginPlaced = true;    // ✅ 이제부터는 XR 시스템이 알아서 움직이게 냅둠

            Debug.Log($"[GameState] XR Origin placed at {pos}, yaw={yaw} (one-time)");
        }

        // ================================================================
        //  Random Character Spawn (Once Only)
        // ================================================================
        private void SpawnRandomCharacters()
        {
            Debug.Log("[GameState] Spawning random characters (once).");

            foreach (var entry in randomCharacters)
            {
                if (entry.prefab == null) continue;

                Vector3 pos;
                if (!FindValidRandomPosition(entry.radius, out pos))
                {
                    Debug.LogWarning($"[GameState] Failed to place random character {entry.prefab.name}");
                    continue;
                }

                entry.instance = Instantiate(entry.prefab, pos, Quaternion.identity);
                Debug.Log($"[GameState] Spawned {entry.prefab.name} at {pos}");
            }
        }


        // ================================================================
        //  Valid Random Position Search
        // ================================================================
        private bool FindValidRandomPosition(float radius, out Vector3 outPos)
        {
            for (int i = 0; i < maxAttempts; i++)
            {
                float x = UnityEngine.Random.Range(_minX, _maxX);
                float z = UnityEngine.Random.Range(_minZ, _maxZ);
                Vector3 p = new Vector3(x, randomHeight, z);

                // 충돌 검사
                if (IsFarFromAllObjects(p, radius))
                {
                    outPos = p;
                    return true;
                }
            }

            outPos = Vector3.zero;
            return false;
        }

        private bool IsFarFromAllObjects(Vector3 pos, float radius)
        {
            float sq = radius * radius;

            // 기존 랜덤 캐릭터
            foreach (var entry in randomCharacters)
            {
                if (entry.instance == null) continue;
                if ((entry.instance.transform.position - pos).sqrMagnitude < sq)
                    return false;
            }

            // 건물 충돌 체크
            foreach (var b in buildingMappings)
            {
                if (b.target == null) continue;
                Vector3 bp = b.target.transform.position;

                if ((bp - pos).sqrMagnitude < sq)
                    return false;
            }

            return true;
        }
    }
}
