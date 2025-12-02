using System;
using System.Collections.Generic;
using UnityEngine;

namespace LegoVR.Mapping
{
    [Serializable]
    public class Vec2Payload
    {
        public float x;
        public float y;
    }

    /// <summary>
    /// Python에서 보내는 objects 배열의 각 원소
    /// </summary>
    [Serializable]
    public class ObjectPayload
    {
        public int id;
        public string kind;   // "building", "character" 등
        public string label;  // ex) "Building_01"

        public Vec2Payload marker_board;
        public Vec2Payload marker_stud;
        public Vec2Payload marker_unity;
        public Vec2Payload spawn_stud;
        public Vec2Payload spawn_unity;

        public float yaw_deg;
    }

    /// <summary>
    /// 루트 payload: { "objects": [ ... ] }
    /// </summary>
    [Serializable]
    public class PayloadRoot
    {
        public List<ObjectPayload> objects;
    }
}
