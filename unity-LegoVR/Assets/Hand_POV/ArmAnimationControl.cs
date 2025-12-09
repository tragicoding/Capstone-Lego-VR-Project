using UnityEngine;

public class ArmAnimationControl : MonoBehaviour
{
    public Animator armAnimator; // 팔 애니메이터
    public Transform playerRoot; // 플레이어의 몸통 (XR Origin)

    private Vector3 lastPosition;
    public float minSpeed = 0.05f; // 이 속도 이상일 때만 걷는 것으로 판정

    void Start()
    {
        // 시작 위치 저장
        if (playerRoot != null) lastPosition = playerRoot.position;
    }

    void Update()
    {
        if (playerRoot == null || armAnimator == null) return;

        // 1. 현재 프레임의 이동 거리 계산 (속도)
        float speed = Vector3.Distance(playerRoot.position, lastPosition) / Time.deltaTime;

        // 2. 일정 속도 이상이면 걷는 것으로 판정
        bool isMoving = speed > minSpeed;

        // 3. 애니메이터에 신호 보내기
        armAnimator.SetBool("isMoving", isMoving);

        // 4. 현재 위치를 다음 프레임 비교용으로 저장
        lastPosition = playerRoot.position;
    }
}