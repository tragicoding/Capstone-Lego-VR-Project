using System.Collections;
using UnityEngine;

public class HeadLookAround : MonoBehaviour
{
    [Header("설정")]
    public float rotationSpeed = 2.0f;   // 회전 속도
    public float maxAngle = 45f;         // 좌우로 얼마나 돌릴지 (범위)
    public float minWaitTime = 1.0f;     // 최소 대기 시간
    public float maxWaitTime = 4.0f;     // 최대 대기 시간

    private float baseAngleY;            // 처음에 설정된 기본 Y 각도 (예: -90)
    private Quaternion targetRotation;

    void Start()
    {
        // 1. 게임 시작 시점의 현재 머리 각도를 기준점으로 저장합니다.
        // 예: 머리가 -90도로 되어있다면 -90이 저장됩니다.
        baseAngleY = transform.localEulerAngles.y;

        StartCoroutine(LookRoutine());
    }

    IEnumerator LookRoutine()
    {
        while (true)
        {
            // 2. 기준점(baseAngleY)에서 +- 랜덤 값을 더합니다.
            // 예: -90 + (random -30 ~ 30) -> -120 ~ -60 사이가 됨
            float randomOffset = Random.Range(-maxAngle, maxAngle);
            float finalY = baseAngleY + randomOffset;

            // X, Z축은 건드리지 않고 Y축만 변경
            targetRotation = Quaternion.Euler(0, finalY, 0);

            // 3. 목표 각도까지 부드럽게 회전
            while (Quaternion.Angle(transform.localRotation, targetRotation) > 0.5f)
            {
                transform.localRotation = Quaternion.Slerp(transform.localRotation, targetRotation, Time.deltaTime * rotationSpeed);
                yield return null;
            }

            // 4. 대기
            float waitTime = Random.Range(minWaitTime, maxWaitTime);
            yield return new WaitForSeconds(waitTime);
        }
    }
}