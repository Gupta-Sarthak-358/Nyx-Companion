import { useEffect, useRef } from 'react'

export function getOrCreateSessionId() {
  let sid = localStorage.getItem('session_id')
  if (!sid) {
    sid = crypto.randomUUID()
    localStorage.setItem('session_id', sid)
  }
  return sid
}

export function useWebSocket({ onStatus, onUserSpeech, onAiToken, onAiResponse, onAudioChunk, onAudioDone, onReport, onSessionRestored, onMcqMessage }) {
  const socketRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const reconnectAttemptRef = useRef(0)
  const sessionIdRef = useRef(getOrCreateSessionId())

  useEffect(() => {
    const connect = () => {
      if (socketRef.current) {
        socketRef.current.onclose = null
        socketRef.current.close()
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.hostname === 'localhost' ? 'localhost:5000' : window.location.host
      const socket = new WebSocket(`${protocol}//${host}/ws/interview`)
      socket.binaryType = 'arraybuffer'
      socketRef.current = socket

      socket.onopen = () => {
        reconnectAttemptRef.current = 0
        onStatus('Connected. Select mode and Start Session.')
      }

      socket.onmessage = (event) => {
        const start = performance.now()
        if (event.data instanceof ArrayBuffer) {
          const buf = new Uint8Array(event.data)
          const type = buf[0]
          if (type === 0x01) {
            const seq = new DataView(event.data).getUint32(1, true)
            const audio = buf.slice(5)
            onAudioChunk({ seq, audio })
          }
          return
        }
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'status':
            onStatus(data.message)
            break
          case 'user_speech':
            onUserSpeech(data)
            break
          case 'ai_token':
            onAiToken(data.token)
            break
          case 'ai_response':
            onAiResponse(data.text)
            if (window.__METRICS) console.log(`[perf] WS ai_response roundtrip: ${(performance.now() - start).toFixed(1)}ms`)
            break
          case 'audio_done':
            onAudioDone?.()
            break
          case 'report':
            onReport(data.data)
            break
          case 'session_restored':
            onSessionRestored?.(data)
            break
          case 'mcq_question':
          case 'mcq_result':
          case 'mcq_summary':
          case 'mcq_error':
            onMcqMessage?.(data)
            break
          default:
            break
        }
      }

      socket.onclose = () => {
        onStatus('Disconnected. Reconnecting...')
        const attempt = reconnectAttemptRef.current
        const delay = Math.min(1000 * Math.pow(2, attempt), 15000)
        reconnectAttemptRef.current = attempt + 1
        reconnectTimerRef.current = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (socketRef.current) socketRef.current.close()
    }
  }, [])

  return { socketRef, sessionIdRef, reconnectAttemptRef }
}
