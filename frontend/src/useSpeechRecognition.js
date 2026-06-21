import { useState, useRef, useEffect } from 'react'

const SILENCE_THRESHOLD = 25
const SILENCE_DURATION = 3500

export function useSpeechRecognition({ socketRef, isSessionActive }) {
  const [isRecording, setIsRecording] = useState(false)
  const [timer, setTimer] = useState(0)
  const [timerActive, setTimerActive] = useState(false)

  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const silenceStartRef = useRef(null)
  const animationFrameRef = useRef(null)

  useEffect(() => {
    let interval
    if (timerActive) {
      interval = setInterval(() => setTimer(t => t + 1), 1000)
    }
    return () => clearInterval(interval)
  }, [timerActive])

  const sendAudioToServer = (blob) => {
    const reader = new FileReader()
    reader.readAsDataURL(blob)
    reader.onloadend = () => {
      const base64data = reader.result.split(',')[1]
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'audio', data: base64data }))
      }
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop()
      }
      mediaRecorderRef.current = null
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }
    setIsRecording(false)
    setTimerActive(false)
  }

  const startRecording = async () => {
    if (!isSessionActive) {
      alert('Session is not active. Start a session before using the microphone.')
      return
    }
    const start = performance.now()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (window.__METRICS) console.log(`[perf] getUserMedia: ${(performance.now() - start).toFixed(1)}ms`)
      mediaRecorderRef.current = new MediaRecorder(stream)
      audioChunksRef.current = []

      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
      }
      const source = audioContextRef.current.createMediaStreamSource(stream)
      analyserRef.current = audioContextRef.current.createAnalyser()
      analyserRef.current.fftSize = 256
      source.connect(analyserRef.current)

      const bufferLength = analyserRef.current.frequencyBinCount
      const dataArray = new Uint8Array(bufferLength)
      silenceStartRef.current = Date.now()

      const checkSilence = () => {
        if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') return
        analyserRef.current.getByteFrequencyData(dataArray)
        let sum = 0
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i]
        const average = sum / bufferLength
        if (average < SILENCE_THRESHOLD) {
          if (Date.now() - silenceStartRef.current > SILENCE_DURATION) {
            stopRecording()
            return
          }
        } else {
          silenceStartRef.current = Date.now()
        }
        animationFrameRef.current = requestAnimationFrame(checkSilence)
      }

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data)
      }
      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' })
        sendAudioToServer(audioBlob)
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
        stream.getTracks().forEach(t => t.stop())
      }
      mediaRecorderRef.current.start()
      setIsRecording(true)
      setTimerActive(true)
      setTimer(0)
      checkSilence()
    } catch (err) {
      console.error('Recording error:', err)
      const msg = err.name === 'NotAllowedError'
        ? 'Microphone access denied. Please allow microphone permissions in your browser and try again.'
        : err.name === 'NotFoundError'
        ? 'No microphone found. Please connect a microphone and try again.'
        : `Microphone error: ${err.message || 'unknown'}`
      alert(msg)
    }
  }

  const toggleRecording = () => {
    if (isRecording) stopRecording()
    else startRecording()
  }

  return { isRecording, timer, toggleRecording, stopRecording, startRecording }
}
