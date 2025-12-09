using UnityEngine;
using UnityEngine.AI;
using System.Collections;
using TMPro;

[RequireComponent(typeof(NavMeshAgent))]
public class WanderingAI : MonoBehaviour
{
    [Header("기본 설정")]
    public Animator animator;
    public Transform player;
    public Collider wanderZone;

    [Header("대화 및 말풍선 설정")]
    public GameObject speechBubble;
    public TextMeshProUGUI bubbleText;

    [Header("플레이어에게 하는 랜덤 대사들")]
    [TextArea]
    public string[] talkToPlayer; // 배열로 변경됨

    [Header("친구(NPC)에게 하는 랜덤 대사들")]
    [TextArea]
    public string[] talkToNPC;    // 배열로 변경됨

    [Header("감지 설정")]
    public float detectionRange = 5.0f;
    public float talkDuration = 3.0f;
    public float talkCooldown = 10.0f;

    private NavMeshAgent agent;
    private bool isPlayerNear = false;
    public bool isTalking = false;
    private float lastTalkTime = -999f;

    void Start()
    {
        agent = GetComponent<NavMeshAgent>();
        if (speechBubble != null) speechBubble.SetActive(false);
        MoveToRandomPosInZone();
    }

    void Update()
    {
        if (isTalking) return;

        // 1. 플레이어 감지 (최우선)
        if (player != null && Vector3.Distance(transform.position, player.position) <= detectionRange)
        {
            HandlePlayerEncounter();
            return;
        }
        else if (isPlayerNear) // 플레이어가 멀어지면
        {
            isPlayerNear = false;
            ResumeMovement();
        }

        // 2. 친구 감지 (플레이어 없을 때만)
        if (!isPlayerNear && CanTalk())
        {
            CheckForFriends();
        }

        // 3. 이동
        if (!agent.pathPending && agent.remainingDistance <= agent.stoppingDistance)
        {
            MoveToRandomPosInZone();
        }
    }

    // --- [상황 1] 플레이어를 만났을 때 ---
    void HandlePlayerEncounter()
    {
        if (!isPlayerNear)
        {
            isPlayerNear = true;
            agent.isStopped = true;
            if (animator) animator.SetBool("isNear", true);

            // 💬 랜덤 대사 뽑기 (플레이어용)
            string randomMsg = GetRandomMessage(talkToPlayer);
            if (bubbleText != null) bubbleText.text = randomMsg;
            if (speechBubble != null) speechBubble.SetActive(true);
        }

        Vector3 lookPos = new Vector3(player.position.x, transform.position.y, player.position.z);
        transform.LookAt(lookPos);
    }

    // --- [상황 2] 친구(NPC)를 만났을 때 ---
    void CheckForFriends()
    {
        Collider[] hitColliders = Physics.OverlapSphere(transform.position, detectionRange);
        foreach (var hit in hitColliders)
        {
            if (hit.gameObject == this.gameObject) continue;

            if (hit.CompareTag("NPC") || (hit.transform.parent != null && hit.transform.parent.CompareTag("NPC")))
            {
                WanderingAI friendAI = hit.GetComponentInParent<WanderingAI>();

                if (friendAI != null && friendAI.CanTalk())
                {
                    StartConversation(friendAI.transform);
                    friendAI.StartConversation(this.transform);
                    break;
                }
            }
        }
    }

    public void StartConversation(Transform partner)
    {
        if (isTalking) return;
        StartCoroutine(TalkRoutine(partner));
    }

    IEnumerator TalkRoutine(Transform targetFriend)
    {
        isTalking = true;
        agent.isStopped = true;
        agent.velocity = Vector3.zero;
        if (animator) animator.SetBool("isNear", true);

        Vector3 lookPos = new Vector3(targetFriend.position.x, transform.position.y, targetFriend.position.z);
        transform.LookAt(lookPos);

        // 💬 랜덤 대사 뽑기 (친구용)
        string randomMsg = GetRandomMessage(talkToNPC);
        if (bubbleText != null) bubbleText.text = randomMsg;
        if (speechBubble != null) speechBubble.SetActive(true);

        yield return new WaitForSeconds(talkDuration);

        lastTalkTime = Time.time;
        isTalking = false;
        ResumeMovement();
    }

    // 배열에서 랜덤으로 문장 하나 꺼내오는 함수
    string GetRandomMessage(string[] list)
    {
        if (list.Length > 0)
        {
            int randomIndex = Random.Range(0, list.Length);
            return list[randomIndex];
        }
        return "..."; // 대사가 비어있으면 점 3개 출력
    }

    public bool CanTalk()
    {
        return !isTalking && (Time.time >= lastTalkTime + talkCooldown);
    }

    void ResumeMovement()
    {
        agent.isStopped = false;
        if (animator) animator.SetBool("isNear", false);
        if (speechBubble != null) speechBubble.SetActive(false);
    }

    void MoveToRandomPosInZone()
    {
        if (wanderZone == null) return;
        Bounds bounds = wanderZone.bounds;
        for (int i = 0; i < 10; i++)
        {
            float rx = Random.Range(bounds.min.x, bounds.max.x);
            float rz = Random.Range(bounds.min.z, bounds.max.z);
            Vector3 target = new Vector3(rx, transform.position.y, rz);
            NavMeshHit hit;
            if (NavMesh.SamplePosition(target, out hit, 5.0f, NavMesh.AllAreas))
            {
                agent.SetDestination(hit.position);
                ResumeMovement();
                return;
            }
        }
    }
}