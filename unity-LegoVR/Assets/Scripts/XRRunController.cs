using UnityEngine;
using UnityEngine.InputSystem; // 인풋 시스템 필수
using UnityEngine.XR.Interaction.Toolkit; // XR 툴킷 필수

public class XRRunController : MonoBehaviour
{
    [Header("필수 연결")]
    public ActionBasedContinuousMoveProvider moveProvider; // 이동을 담당하는 컴포넌트

    [Header("입력 설정 (왼쪽 스틱 클릭 권장)")]
    public InputActionProperty runInputSource; // 달리기 버튼

    [Header("속도 설정")]
    public float walkSpeed = 2.0f; // 평소 걷는 속도
    public float runSpeed = 6.0f;  // 달리기 속도

    void Update()
    {
        if (moveProvider == null) return;

        // 1. 달리기 버튼을 눌렀는지 확인 (1이면 눌림, 0이면 안 눌림)
        float isPressed = runInputSource.action.ReadValue<float>();

        // 2. 눌렀으면 달리기 속도, 뗐으면 걷기 속도 적용
        if (isPressed > 0.5f)
        {
            moveProvider.moveSpeed = runSpeed;
        }
        else
        {
            moveProvider.moveSpeed = walkSpeed;
        }
    }
}