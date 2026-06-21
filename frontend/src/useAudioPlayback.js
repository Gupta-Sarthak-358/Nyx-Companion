import { useRef, useState } from 'react'

export function useAudioPlayback() {
  const audioRef = useRef(null)
  const audioQueueRef = useRef([])
  const nextAudioSeqRef = useRef(0)
  const isPlayingRef = useRef(false)
  const [isAiSpeaking, setIsAiSpeaking] = useState(false)

  const processAudioQueue = () => {
    if (isPlayingRef.current) return
    const queue = audioQueueRef.current
    while (queue.length > 0 && queue[0].seq === nextAudioSeqRef.current) {
      const chunk = queue.shift()
      const audioBlob = new Blob([chunk.audio], { type: 'audio/wav' })
      const url = URL.createObjectURL(audioBlob)
      if (audioRef.current) {
        isPlayingRef.current = true
        audioRef.current.src = url
        setIsAiSpeaking(true)
        audioRef.current.play().catch(e => {
          console.error("Audio play failed:", e)
          setIsAiSpeaking(false)
          isPlayingRef.current = false
          processAudioQueue()
        })
        audioRef.current.onended = () => {
          setIsAiSpeaking(false)
          isPlayingRef.current = false
          processAudioQueue()
        }
      }
      nextAudioSeqRef.current++
    }
  }

  const MAX_QUEUE = 20

  const enqueueAudio = (data) => {
    const start = performance.now()
    const queue = audioQueueRef.current
    queue.push({ seq: data.seq, audio: data.audio })
    queue.sort((a, b) => a.seq - b.seq)
    while (queue.length > MAX_QUEUE) queue.shift()
    processAudioQueue()
    if (window.__METRICS) console.log(`[perf] Audio enqueue #${data.seq}: ${(performance.now() - start).toFixed(1)}ms`)
  }

  const resetQueue = () => {
    audioQueueRef.current = []
    nextAudioSeqRef.current = 0
  }

  return { audioRef, isAiSpeaking, enqueueAudio, processAudioQueue, resetQueue }
}
