using UnityEngine;

public class SkyboxRotator : MonoBehaviour
{
    [Tooltip("하늘이 회전하는 속도입니다.")]
    public float rotationSpeed = 1.0f;

    void Update()
    {
        // 현재 씬에 적용된 스카이박스 재질(Material)을 가져와서 Rotation 값을 변경
        // "_Rotation"은 유니티 스카이박스 쉐이더의 내부 변수 이름입니다.
        RenderSettings.skybox.SetFloat("_Rotation", Time.time * rotationSpeed);
    }
}