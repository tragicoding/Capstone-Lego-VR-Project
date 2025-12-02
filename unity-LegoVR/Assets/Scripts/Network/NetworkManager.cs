using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;

namespace LegoVR.Network
{
    /// <summary>
    /// Python TCP 서버(vision-python)와 연결해서
    /// 한 줄 단위(JSON)로 메시지를 받아오는 네트워크 매니저.
    /// </summary>
    public class NetworkManager : MonoBehaviour
    {
        [Header("Server Settings")]
        public string serverIp = "127.0.0.1";
        public int serverPort = 5000;

        [Header("Debug")]
        public bool autoConnectOnStart = true;

        private Thread _thread;
        private TcpClient _client;
        private StreamReader _reader;
        private volatile bool _running;

        // 수신된 메시지를 메인 스레드에서 처리하기 위한 큐
        private readonly ConcurrentQueue<string> _messageQueue =
            new ConcurrentQueue<string>();

        public event Action<string> OnMessageReceived;

        private void Start()
        {
            if (autoConnectOnStart)
            {
                StartClient();
            }
        }

        private void OnDestroy()
        {
            StopClient();
        }

        public void StartClient()
        {
            if (_running)
                return;

            _running = true;
            _thread = new Thread(NetworkLoop)
            {
                IsBackground = true
            };
            _thread.Start();
        }

        public void StopClient()
        {
            _running = false;

            try
            {
                _reader?.Close();
            }
            catch { }

            try
            {
                _client?.Close();
            }
            catch { }

            _reader = null;
            _client = null;

            if (_thread != null && _thread.IsAlive)
            {
                try
                {
                    _thread.Join(200);
                }
                catch { }
            }

            _thread = null;
        }

        private void NetworkLoop()
        {
            while (_running)
            {
                try
                {
                    Debug.Log($"[Network] Connecting to {serverIp}:{serverPort} ...");
                    _client = new TcpClient();
                    _client.Connect(serverIp, serverPort);
                    _reader = new StreamReader(_client.GetStream());
                    Debug.Log("[Network] Connected");

                    while (_running && _client.Connected)
                    {
                        string line = _reader.ReadLine(); // '\n' 기준 한 줄
                        if (line == null)
                        {
                            // 서버가 연결 종료
                            break;
                        }

                        _messageQueue.Enqueue(line);
                    }
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[Network] Receive error: {e.Message}");
                }

                // 연결이 끊어졌으면 잠깐 쉰 뒤 재시도
                try
                {
                    _reader?.Close();
                }
                catch { }

                try
                {
                    _client?.Close();
                }
                catch { }

                _reader = null;
                _client = null;

                if (_running)
                {
                    Debug.Log("[Network] Disconnected. Retry in 1 sec...");
                    Thread.Sleep(1000);
                }
            }

            Debug.Log("[Network] NetworkLoop stopped.");
        }

        private void Update()
        {
            // 메인 스레드에서 큐 처리
            while (_messageQueue.TryDequeue(out string msg))
            {
                OnMessageReceived?.Invoke(msg);
            }
        }
    }
}
