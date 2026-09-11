import { useState, useEffect, useRef } from 'react'
import { useCaseStore } from '../store/useCaseStore'
import { getApiUrl } from '../services/api'

const API_BASE: string = getApiUrl('/api')


interface UseVADProps {
  enabled: boolean
  threshold?: number
  silenceDurationMs?: number
}

export function useVAD({ enabled, threshold = 0.04, silenceDurationMs = 1500 }: UseVADProps) {
  const [listening, setListening] = useState(false)
  const [muted, setMuted] = useState(false)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const reqFrameRef = useRef<number>()

  // Voice capture state
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<BlobPart[]>([])
  const isRecordingRef = useRef(false)
  const silenceStartRef = useRef<number | null>(null)

  useEffect(() => {
    if (!enabled || muted) {
      setListening(false)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
        streamRef.current = null
      }
      if (audioContextRef.current) {
        audioContextRef.current.close()
        audioContextRef.current = null
      }
      if (reqFrameRef.current) {
        cancelAnimationFrame(reqFrameRef.current)
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
      return
    }

    let isMounted = true

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        if (!isMounted) return
        streamRef.current = stream
        
        // Setup MediaRecorder
        const mediaRecorder = new MediaRecorder(stream)
        mediaRecorderRef.current = mediaRecorder
        
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            audioChunksRef.current.push(e.data)
          }
        }
        
        mediaRecorder.onstop = () => {
          const blob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType })
          audioChunksRef.current = []
          
          const state = useCaseStore.getState()
          const caseId = state.activeCase?.case_id || 'demo'
          const currentZone = state.uiState.focusedZone || state.activeCase?.zone_id || 'Bay3'
          
          // Only send if it has some duration
          if (blob.size > 1000) {
            const formData = new FormData()
            formData.append('audio', blob, 'voice.webm')
            formData.append('case_id', caseId)
            formData.append('current_zone', currentZone)
            
            fetch(`${API_BASE}/voice/command`, {
              method: 'POST',
              body: formData
            }).catch(console.error)
          }
        }

        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
        audioContextRef.current = audioContext
        
        const analyser = audioContext.createAnalyser()
        analyser.fftSize = 512
        analyser.smoothingTimeConstant = 0.5
        analyserRef.current = analyser

        const source = audioContext.createMediaStreamSource(stream)
        source.connect(analyser)
        sourceRef.current = source

        const dataArray = new Float32Array(analyser.fftSize)

        const checkAudioLevel = () => {
          if (!analyserRef.current) return
          analyserRef.current.getFloatTimeDomainData(dataArray)
          
          let sumSquares = 0.0
          for (const amplitude of dataArray) {
            sumSquares += amplitude * amplitude
          }
          const rms = Math.sqrt(sumSquares / dataArray.length)

          const isCurrentlySpeaking = rms > threshold && !(window as any)._isRimeSpeaking
          
          if (isCurrentlySpeaking) {
             setListening(true)
             silenceStartRef.current = null
             if (!isRecordingRef.current) {
                 isRecordingRef.current = true
                 audioChunksRef.current = []
                 mediaRecorderRef.current?.start()
             }
          } else {
             if (isRecordingRef.current) {
                 if (silenceStartRef.current === null) {
                     silenceStartRef.current = Date.now()
                 } else if (Date.now() - silenceStartRef.current > silenceDurationMs) {
                     // Silence duration exceeded, stop recording
                     isRecordingRef.current = false
                     setListening(false)
                     mediaRecorderRef.current?.stop()
                     silenceStartRef.current = null
                 }
             } else {
                 setListening(false)
             }
          }

          reqFrameRef.current = requestAnimationFrame(checkAudioLevel)
        }
        
        checkAudioLevel()
      })
      .catch(err => {
        console.error("Microphone access denied or error:", err)
      })

    return () => {
      isMounted = false
      if (reqFrameRef.current) cancelAnimationFrame(reqFrameRef.current)
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
      if (audioContextRef.current) audioContextRef.current.close()
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
          mediaRecorderRef.current.stop()
      }
    }
  }, [enabled, muted, threshold, silenceDurationMs])

  return {
    listening,
    muted,
    toggleMute: () => setMuted(!muted)
  }
}
