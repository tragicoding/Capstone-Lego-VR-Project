using UnityEngine;
using UnityEngine.InputSystem; // 입력 시스템 사용

public class Jetpack : MonoBehaviour
{
    [Header("설정")]
    public float flySpeed = 5.0f; // 비행 속도
    public CharacterController characterController; // 플레이어 몸체
    public InputActionProperty jumpInput; // 점프 버튼 입력

    void Update()
    {
        // 점프 버튼을 꾹 누르고 있으면 (값이 0보다 크면)
        if (jumpInput.action != null && jumpInput.action.ReadValue<float>() > 0.1f)
        {
            // 위쪽 방향으로 계속 이동시킨다
            characterController.Move(Vector3.up * flySpeed * Time.deltaTime);
        }
    }
}