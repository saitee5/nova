/**
 * frontend/src/services/voiceService.ts — Industrial Voice Service for NOVA.
 *
 * Provides:
 * 1. Low-latency Streaming TTS via Rime API (/api/voice/stream) with browser SpeechSynthesis fallback.
 * 2. Real-time Speech-to-Text via Web Speech API (SpeechRecognition / webkitSpeechRecognition)
 *    and MediaRecorder upload fallback (/api/voice/transcribe).
 * 3. Immediate Barge-In (Audio cancellation + backend abort).
 * 4. Latency monitoring for industrial control room KPIs.
 */

// Strip markdown, asterisks, brackets, and code blocks for crisp speech delivery
export function cleanSpokenText(text: string): string {
  if (!text) return ''
  return text
    .replace(/```[\s\S]*?```/g, '') // remove code blocks
    .replace(/`([^`]+)`/g, '$1') // inline code
    .replace(/\*\*(.*?)\*\*/g, '$1') // bold
    .replace(/\*(.*?)\*/g, '$1') // italic
    .replace(/#+\s*/g, '') // headers
    .replace(/\[(.*?)\]\(.*?\)/g, '$1') // links
    .replace(/[*_~`[\]{}>]/g, '') // remaining markdown chars
    .replace(/[\n\r]+/g, '. ') // newlines to sentence pauses
    .replace(/\s+/g, ' ') // collapse whitespaces
    .trim()
}

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking'

class VoiceService {
  private currentAudio: HTMLAudioElement | null = null
  private activeRecognition: any = null
  private mediaRecorder: MediaRecorder | null = null
  private recordedChunks: Blob[] = []
  private isSpeakingActive = false
  private isListeningActive = false
  private lastLatencyMs: number | null = null

  /**
   * Play speech using the low-latency Rime TTS streaming endpoint.
   * Automatically falls back to Web Speech API if offline or blocked.
   */
  public async playSpeech(
    rawText: string,
    callbacks?: {
      onStart?: () => void
      onEnd?: () => void
      onError?: (err: unknown) => void
      onLatency?: (latencyMs: number) => void
    }
  ): Promise<void> {
    const text = cleanSpokenText(rawText)
    if (!text) return

    // Stop any existing utterance (barge-in previous audio)
    this.cancelSpeech()

    const startTime = performance.now()
    this.isSpeakingActive = true

    try {
      const streamUrl = `/api/voice/stream?text=${encodeURIComponent(text)}&t=${Date.now()}`
      const audio = new Audio(streamUrl)
      this.currentAudio = audio

      audio.onplay = () => {
        const ttfb = Math.round(performance.now() - startTime)
        this.lastLatencyMs = ttfb
        callbacks?.onLatency?.(ttfb)
        callbacks?.onStart?.()
      }

      audio.onended = () => {
        this.isSpeakingActive = false
        this.currentAudio = null
        callbacks?.onEnd?.()
      }

      audio.onerror = (e) => {
        console.warn('Rime streaming TTS audio playback error, falling back to browser synthesis:', e)
        this.fallbackSpeechSynthesis(text, callbacks)
      }

      await audio.play()
    } catch (err) {
      console.warn('Failed to start Rime TTS stream, using browser fallback:', err)
      this.fallbackSpeechSynthesis(text, callbacks)
    }
  }

  /**
   * Fallback using browser Web Speech Synthesis.
   */
  private fallbackSpeechSynthesis(
    text: string,
    callbacks?: {
      onStart?: () => void
      onEnd?: () => void
      onError?: (err: unknown) => void
    }
  ): void {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      this.isSpeakingActive = false
      callbacks?.onEnd?.()
      return
    }

    try {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 1.05
      utterance.pitch = 1.0
      utterance.lang = 'en-US'

      // Pick an English natural voice if available
      const voices = window.speechSynthesis.getVoices()
      const naturalVoice = voices.find(
        (v) => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('Google') || v.name.includes('Samantha'))
      ) || voices.find((v) => v.lang.startsWith('en'))
      if (naturalVoice) utterance.voice = naturalVoice

      utterance.onstart = () => {
        this.isSpeakingActive = true
        callbacks?.onStart?.()
      }

      utterance.onend = () => {
        this.isSpeakingActive = false
        callbacks?.onEnd?.()
      }

      utterance.onerror = (e) => {
        this.isSpeakingActive = false
        callbacks?.onError?.(e)
        callbacks?.onEnd?.()
      }

      window.speechSynthesis.speak(utterance)
    } catch (err) {
      this.isSpeakingActive = false
      callbacks?.onError?.(err)
      callbacks?.onEnd?.()
    }
  }

  /**
   * Instant Barge-In:
   * Aborts client audio playback immediately and notifies the backend to cancel stream generation.
   */
  public cancelSpeech(): void {
    this.isSpeakingActive = false

    if (this.currentAudio) {
      try {
        this.currentAudio.pause()
        this.currentAudio.currentTime = 0
        this.currentAudio.src = ''
      } catch {
        // ignore
      }
      this.currentAudio = null
    }

    if (typeof window !== 'undefined' && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel()
      } catch {
        // ignore
      }
    }

    // Notify backend
    fetch('/api/voice/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_id: 'live-copilot' }),
    }).catch(() => {})
  }

  /**
   * Start listening for voice input.
   * Supports Web Speech Recognition with fallback to MediaRecorder.
   */
  public startListening(callbacks: {
    onStart?: () => void
    onResult: (transcript: string, isFinal: boolean) => void
    onError?: (err: unknown) => void
    onEnd?: () => void
  }): boolean {
    this.cancelSpeech() // Barge-in if currently speaking

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition()
        recognition.continuous = false
        recognition.interimResults = true
        recognition.lang = 'en-US'

        recognition.onstart = () => {
          this.isListeningActive = true
          callbacks.onStart?.()
        }

        recognition.onresult = (event: any) => {
          let interimTranscript = ''
          let finalTranscript = ''

          for (let i = event.resultIndex; i < event.results.length; ++i) {
            const result = event.results[i]
            if (result.isFinal) {
              finalTranscript += result[0].transcript
            } else {
              interimTranscript += result[0].transcript
            }
          }

          if (finalTranscript.trim()) {
            callbacks.onResult(finalTranscript.trim(), true)
          } else if (interimTranscript.trim()) {
            callbacks.onResult(interimTranscript.trim(), false)
          }
        }

        recognition.onerror = (err: any) => {
          console.warn('SpeechRecognition error:', err)
          this.isListeningActive = false
          callbacks.onError?.(err)
          callbacks.onEnd?.()
        }

        recognition.onend = () => {
          this.isListeningActive = false
          this.activeRecognition = null
          callbacks.onEnd?.()
        }

        this.activeRecognition = recognition
        recognition.start()
        return true
      } catch (err) {
        console.warn('Failed to start SpeechRecognition, trying microphone recorder:', err)
      }
    }

    // Fallback to MediaRecorder & backend /api/voice/transcribe
    this.startMediaRecorder(callbacks)
    return true
  }

  /**
   * Microphone recording fallback for browsers lacking SpeechRecognition.
   */
  private async startMediaRecorder(callbacks: {
    onStart?: () => void
    onResult: (transcript: string, isFinal: boolean) => void
    onError?: (err: unknown) => void
    onEnd?: () => void
  }): Promise<void> {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      callbacks.onError?.(new Error('Microphone access is not supported on this browser.'))
      callbacks.onEnd?.()
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      this.recordedChunks = []
      const recorder = new MediaRecorder(stream)

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          this.recordedChunks.push(e.data)
        }
      }

      recorder.onstart = () => {
        this.isListeningActive = true
        callbacks.onStart?.()
      }

      recorder.onstop = async () => {
        this.isListeningActive = false
        stream.getTracks().forEach((track) => track.stop())

        if (this.recordedChunks.length === 0) {
          callbacks.onEnd?.()
          return
        }

        const audioBlob = new Blob(this.recordedChunks, { type: 'audio/webm' })
        const formData = new FormData()
        formData.append('audio', audioBlob, 'mic_recording.webm')

        try {
          const res = await fetch('/api/voice/transcribe', {
            method: 'POST',
            body: formData,
          })
          if (res.ok) {
            const data = await res.json()
            if (data.transcript && data.transcript.trim()) {
              callbacks.onResult(data.transcript.trim(), true)
            }
          }
        } catch (err) {
          callbacks.onError?.(err)
        } finally {
          callbacks.onEnd?.()
        }
      }

      this.mediaRecorder = recorder
      recorder.start()
    } catch (err) {
      this.isListeningActive = false
      callbacks.onError?.(err)
      callbacks.onEnd?.()
    }
  }

  public stopListening(): void {
    if (this.activeRecognition) {
      try {
        this.activeRecognition.stop()
      } catch {
        // ignore
      }
      this.activeRecognition = null
    }

    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      try {
        this.mediaRecorder.stop()
      } catch {
        // ignore
      }
      this.mediaRecorder = null
    }

    this.isListeningActive = false
  }

  public getLatency(): number | null {
    return this.lastLatencyMs
  }

  public isSpeaking(): boolean {
    return this.isSpeakingActive
  }

  public isListening(): boolean {
    return this.isListeningActive
  }
}

export const voiceService = new VoiceService()
