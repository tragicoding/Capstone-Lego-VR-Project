using System;
using System.Collections.Generic;

namespace LegoVR.Network
{
    [Serializable]
    public class Vec2
    {
        public float x;
        public float y;
    }

    [Serializable]
    public class ObjectPayload
    {
        public int id;           // 5
        public string kind;      // "building" 또는 "character"
        public string label;     // "Building_02" 등

        public Vec2 marker_board;
        public Vec2 marker_stud;
        public Vec2 marker_unity;

        public Vec2 spawn_stud;
        public Vec2 spawn_unity;

        public float yaw_deg;    // 회전 (도 단위, Y축)
    }

    [Serializable]
    public class PayloadRoot
    {
        public List<ObjectPayload> objects;
    }
}
