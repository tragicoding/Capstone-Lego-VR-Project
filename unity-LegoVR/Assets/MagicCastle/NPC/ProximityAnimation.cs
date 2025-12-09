using UnityEngine;
using TMPro; // 글자(TMP) 쓰려면 필수

public class StaticNPC : MonoBehaviour
{
    [Header("기본 설정")]
    public Animator npcAnimator;   // 캐릭터 애니메이터
    public Transform player;       // 플레이어 (XR Origin)
    public float detectionRange = 3.0f; // 감지 거리 (미터)

    [Header("말풍선 설정")]
    public GameObject speechBubble;       // 말풍선 오브젝트 (Canvas/Image)
    public TextMeshProUGUI bubbleText;    // 말풍선 안의 글자 (TMP)

    [Header("랜덤 대사 리스트")]
    [TextArea] // 인스펙터에서 글쓰기 편하게 창을 넓혀줌
    public string[] sentences; // 대사들을 담을 배열 (여러 개 가능)

    private bool isNear = false; // 현재 가까이 있는 상태인가?

    void Start()
    {
        // 시작할 때 말풍선 끄기
        if (speechBubble != null) speechBubble.SetActive(false);
    }

    void Update()
    {
        if (player == null) return;

        // 1. 거리 계산
        float distance = Vector3.Distance(transform.position, player.position);

        // 2. 범위 안에 들어왔을 때 (입장)
        if (distance <= detectionRange)
        {
            if (!isNear) // "어? 방금 들어왔네?" (딱 한 번만 실행)
            {
                isNear = true;

                // 애니메이션 켜기
                if (npcAnimator != null) npcAnimator.SetBool("isNear", true);

                // 말풍선 켜기 및 랜덤 대사 뽑기
                ShowRandomMessage();
            }

            // 플레이어 쳐다보기 (선택 사항)
            Vector3 lookPos = new Vector3(player.position.x, transform.position.y, player.position.z);
            transform.LookAt(lookPos);
        }
        // 3. 범위 밖으로 나갔을 때 (퇴장)
        else
        {
            if (isNear) // "어? 방금 나갔네?" (딱 한 번만 실행)
            {
                isNear = false;

                // 애니메이션 끄기
                if (npcAnimator != null) npcAnimator.SetBool("isNear", false);

                // 말풍선 끄기
                if (speechBubble != null) speechBubble.SetActive(false);
            }
        }
    }

    void ShowRandomMessage()
    {
        // 대사가 하나라도 있을 때만 실행
        if (sentences.Length > 0 && bubbleText != null)
        {
            // 0번부터 개수(Length) 사이의 랜덤 숫자 뽑기
            int randomIndex = Random.Range(0, sentences.Length);

            // 뽑힌 대사를 말풍선에 넣기
            bubbleText.text = sentences[randomIndex];

            // 말풍선 켜기
            if (speechBubble != null) speechBubble.SetActive(true);
        }
    }

    // 에디터에서 범위 눈으로 보기
    void OnDrawGizmosSelected()
    {
        Gizmos.color = Color.cyan;
        Gizmos.DrawWireSphere(transform.position, detectionRange);
    }
}