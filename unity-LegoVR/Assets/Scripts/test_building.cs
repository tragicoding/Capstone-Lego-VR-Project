using UnityEngine;
using LegoVR.Mapping;

public class TestPlaceBuilding : MonoBehaviour
{
    public GridMapper gridMapper;
    public Transform targetBuilding;
    public int gridX = 1;
    public int gridY = 1;

    private void Start()
    {
        if (gridMapper == null || targetBuilding == null) return;

        Vector3 pos = gridMapper.GridToWorld(gridX, gridY, 0f);
        Debug.Log($"[TestPlace] grid=({gridX},{gridY}) -> world={pos}");
        targetBuilding.position = pos;
    }
}
