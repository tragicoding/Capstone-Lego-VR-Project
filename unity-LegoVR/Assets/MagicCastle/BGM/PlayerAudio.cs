using UnityEngine;

[RequireComponent(typeof(AudioSource))]
public class PlayerAudio : MonoBehaviour
{
    [Header("오디오 파일")]
    public AudioClip walkClip;
    public AudioClip jumpClip;

    [Header("민감도 조절 (이 숫자를 조절하세요)")]
    // 이 속도보다 느리면 '멈춤'으로 간주합니다. (기존 0.5 -> 1.5로 올림)
    public float walkSpeedThreshold = 1.5f;
    public float stepInterval = 0.5f;

    private AudioSource audioSource;
    private CharacterController characterController;
    private float stepTimer = 0f;
    private Vector3 lastPosition;
    private bool wasGrounded = true;

    void Start()
    {
        audioSource = GetComponent<AudioSource>();
        characterController = GetComponentInParent<CharacterController>();
        lastPosition = transform.position;
    }

    void Update()
    {
        // 1. 현재 속도 계산 (높이 Y축 제외, 수평 움직임만 계산)
        Vector3 currentPos = transform.position;
        // X, Z 축만으로 거리를 재서 불필요한 고개 움직임(Y) 무시
        float distanceMoved = Vector3.Distance(new Vector3(currentPos.x, 0, currentPos.z), new Vector3(lastPosition.x, 0, lastPosition.z));
        float speed = distanceMoved / Time.deltaTime;

        // 디버깅용: 콘솔창에 현재 속도를 보여줍니다. (숫자가 너무 크면 Threshold를 더 올리세요)
        // Debug.Log($"현재 속도: {speed}"); 

        // 2. 걷기 소리 로직
        // "속도가 설정값보다 빠르고" AND "땅에 붙어있을 때"만 소리 재생
        bool isMoving = speed > walkSpeedThreshold;

        if (isMoving && wasGrounded)
        {
            stepTimer += Time.deltaTime;
            if (stepTimer >= stepInterval)
            {
                // 랜덤 피치 (소리를 약간 다르게 해서 자연스럽게)
                audioSource.pitch = Random.Range(0.9f, 1.1f);
                audioSource.PlayOneShot(walkClip, 0.2f);
                stepTimer = 0f;
            }
        }
        else
        {
            // 멈추면 타이머 초기화 (다시 걸을 때 바로 소리 나게)
            stepTimer = stepInterval;
        }

        // 3. 점프 소리 (갑자기 Y축이 쑥 올라갈 때)
        if (currentPos.y > lastPosition.y + 0.05f && wasGrounded)
        {
            audioSource.pitch = 1.0f; // 점프는 정속도로
            audioSource.PlayOneShot(jumpClip, 0.2f);
            wasGrounded = false;
        }

        // 땅 체크
        if (characterController != null)
        {
            if (characterController.isGrounded) wasGrounded = true;
        }
        else if (transform.position.y < 1.05f) // 단순 높이 체크 보완
        {
            wasGrounded = true;
        }

        lastPosition = currentPos;
    }
}