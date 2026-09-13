import React, { useState, useRef, useEffect } from 'react'
import {
  X,
  Sparkles,
  Mic,
  MicOff,
  Send,
  CheckCircle2,
  Volume2,
  VolumeX,
  ShieldCheck,
  Radio,
  Square,
  Zap,
} from 'lucide-react'
import { useRealtimeStore } from '../../stores/useRealtimeStore'
import { voiceService } from '../../services/voiceService'
import { Button } from '../common/Button'

export const NovaCopilot: React.FC = () => {
  const isCopilotOpen = useRealtimeStore((s) => s.isCopilotOpen)
  const closeCopilot = useRealtimeStore((s) => s.closeCopilot)
  const messages = useRealtimeStore((s) => s.copilotMessages)
  const streaming = useRealtimeStore((s) => s.copilotStreaming)
  const voiceState = useRealtimeStore((s) => s.voiceState)
  const setVoiceState = useRealtimeStore((s) => s.setVoiceState)
  const autoSpeakVoice = useRealtimeStore((s) => s.autoSpeakVoice)
  const toggleAutoSpeakVoice = useRealtimeStore((s) => s.toggleAutoSpeakVoice)
  const voiceLatencyMs = useRealtimeStore((s) => s.voiceLatencyMs)
  const speakCopilotMessage = useRealtimeStore((s) => s.speakCopilotMessage)
  const bargeInVoice = useRealtimeStore((s) => s.bargeInVoice)
  const sendMessage = useRealtimeStore((s) => s.sendUserMessage)
  const approveRecommendation = useRealtimeStore((s) => s.approveRecommendation)
  const selectedEquipmentId = useRealtimeStore((s) => s.selectedEquipmentId)
  const equipment = useRealtimeStore((s) =>
    selectedEquipmentId ? s.equipment[selectedEquipmentId] : null
  )

  const [inputVal, setInputVal] = useState('')
  const [interimText, setInterimText] = useState('')
  const [currentlySpeakingMsgId, setCurrentlySpeakingMsgId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isCopilotOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isCopilotOpen, streaming, interimText])

  if (!isCopilotOpen) return null

  const handleSend = (textToSend?: string) => {
    const text = (textToSend !== undefined ? textToSend : inputVal).trim()
    if (!text) return
    sendMessage(text)
    setInputVal('')
    setInterimText('')
  }

  // Voice Interaction: Toggle STT / Barge-in
  const handleVoiceToggle = () => {
    if (voiceState === 'speaking') {
      // Instant Barge-In: interrupt speech immediately
      bargeInVoice()
      setCurrentlySpeakingMsgId(null)
      return
    }

    if (voiceState === 'listening') {
      // User tapped mic while listening: stop listening
      voiceService.stopListening()
      setVoiceState('idle')
      setInterimText('')
      return
    }

    // Start Listening
    setInterimText('')
    setVoiceState('listening')

    voiceService.startListening({
      onStart: () => {
        setVoiceState('listening')
      },
      onResult: (transcript, isFinal) => {
        if (isFinal) {
          setInterimText('')
          setInputVal(transcript)
          setVoiceState('processing')
          // Auto send and speak response
          sendMessage(transcript, true).finally(() => {
            if (voiceService.isSpeaking()) {
              setVoiceState('speaking')
            } else {
              setVoiceState('idle')
            }
          })
        } else {
          setInterimText(transcript)
        }
      },
      onError: (err) => {
        console.warn('Voice input error:', err)
        setVoiceState('idle')
        setInterimText('')
      },
      onEnd: () => {
        if (useRealtimeStore.getState().voiceState === 'listening') {
          setVoiceState('idle')
        }
      },
    })
  }

  const handlePlayMessageVoice = (msgId: string, text: string) => {
    if (currentlySpeakingMsgId === msgId && voiceState === 'speaking') {
      bargeInVoice()
      setCurrentlySpeakingMsgId(null)
      return
    }

    setCurrentlySpeakingMsgId(msgId)
    speakCopilotMessage(text).finally(() => {
      setCurrentlySpeakingMsgId(null)
    })
  }

  const quickPrompts = [
    { label: 'Status & Alarms', prompt: 'What is the operational status and active alarms for F-201A?' },
    { label: 'Tube Temp Risk', prompt: 'Analyze radiant tube skin temperature anomaly and run ML surrogate.' },
    { label: 'Emergency SOP', prompt: 'What is the standard operating emergency procedure for furnace trip?' },
  ]

  return (
    <div className="fixed top-0 right-0 bottom-0 w-full sm:w-[460px] bg-white border-l border-slate-200 shadow-2xl z-50 flex flex-col transition-all duration-300 animate-in slide-in-from-right font-sans">
      {/* ── Header ── */}
      <div className="p-4 border-b border-slate-200 bg-slate-50/90 flex items-center justify-between backdrop-blur-xs">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center text-white shadow-xs">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-slate-900">NOVA Voice Copilot</span>
              <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-emerald-100 text-emerald-800 rounded border border-emerald-200 flex items-center gap-1">
                <Radio className="w-2.5 h-2.5 text-emerald-600 animate-pulse" />
                RIME TTS LIVE
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-mono">
              Petrochemical Reasoning & Voice Agent
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Auto-Speak Toggle */}
          <button
            onClick={toggleAutoSpeakVoice}
            title={autoSpeakVoice ? 'Audio Output: Active (Click to Mute)' : 'Audio Output: Muted (Click to Unmute)'}
            className={`p-1.5 rounded-md border transition-colors cursor-pointer ${
              autoSpeakVoice
                ? 'bg-orange-50 text-orange-600 border-orange-200 hover:bg-orange-100'
                : 'bg-slate-100 text-slate-400 border-slate-200 hover:bg-slate-200'
            }`}
          >
            {autoSpeakVoice ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>

          {/* Close Copilot */}
          <button
            onClick={() => {
              bargeInVoice()
              closeCopilot()
            }}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* ── Target Equipment / Bay Context Strip ── */}
      <div className="px-4 py-2 bg-orange-50/60 border-b border-orange-200/60 flex items-center justify-between text-xs font-mono">
        <span className="text-slate-600">
          Target Asset:{' '}
          <strong className="text-orange-900">
            {equipment ? `${equipment.tag} (${equipment.name})` : 'F-201A Crude Charge Furnace'}
          </strong>
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-orange-300 text-orange-800 font-bold flex items-center gap-1">
          <Zap className="w-2.5 h-2.5 text-orange-600" />
          {equipment ? `Risk: ${equipment.riskScore}/100` : 'Bay 3 Active'}
        </span>
      </div>

      {/* ── Live Voice Status Indicator Bar ── */}
      <div
        className={`px-4 py-2 border-b flex items-center justify-between text-xs transition-colors ${
          voiceState === 'listening'
            ? 'bg-amber-50 border-amber-200 text-amber-900'
            : voiceState === 'speaking'
            ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
            : voiceState === 'processing'
            ? 'bg-orange-50 border-orange-200 text-orange-900'
            : 'bg-slate-50 border-slate-200 text-slate-600'
        }`}
      >
        <div className="flex items-center gap-2">
          {voiceState === 'listening' ? (
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-3 bg-amber-500 rounded-full animate-pulse" />
              <span className="w-1.5 h-4 bg-amber-600 rounded-full animate-pulse delay-75" />
              <span className="w-1.5 h-2.5 bg-amber-500 rounded-full animate-pulse delay-150" />
            </div>
          ) : voiceState === 'speaking' ? (
            <Volume2 className="w-4 h-4 text-emerald-600 animate-bounce" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-slate-400" />
          )}

          <span className="font-mono text-[11px] font-semibold">
            {voiceState === 'listening'
              ? 'LISTENING — Speak your command...'
              : voiceState === 'speaking'
              ? 'NOVA SPEAKING — Click Mic for Barge-In'
              : voiceState === 'processing'
              ? 'REASONING OVER SIGNALS...'
              : 'VOICE AGENT IDLE'}
          </span>
        </div>

        <div className="flex items-center gap-2 font-mono text-[10px] text-slate-500">
          <span>Latency: {voiceLatencyMs || 142}ms</span>
        </div>
      </div>

      {/* ── Message Log ── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.sender === 'user' ? 'items-end' : 'items-start'
            }`}
          >
            <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono mb-1">
              <span>{msg.sender === 'user' ? 'Operator' : 'NOVA Agent'}</span>
              <span>•</span>
              <span>{msg.timestamp}</span>
              {msg.sender === 'nova' && (
                <button
                  onClick={() => handlePlayMessageVoice(msg.id, msg.text)}
                  title={currentlySpeakingMsgId === msg.id && voiceState === 'speaking' ? 'Stop Audio' : 'Speak Message Aloud'}
                  className="ml-1 p-1 hover:text-orange-600 rounded hover:bg-slate-200/50 transition-colors cursor-pointer"
                >
                  {currentlySpeakingMsgId === msg.id && voiceState === 'speaking' ? (
                    <Square className="w-3 h-3 text-red-500 fill-red-500" />
                  ) : (
                    <Volume2 className="w-3 h-3 text-slate-500 hover:text-orange-600" />
                  )}
                </button>
              )}
            </div>

            <div
              className={`p-3 rounded-xl max-w-[92%] leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-gradient-to-r from-orange-500 to-amber-600 text-white font-medium rounded-tr-none shadow-xs'
                  : 'bg-slate-100 border border-slate-200 text-slate-800 rounded-tl-none'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
            </div>

            {/* Structured Recommendation Card */}
            {msg.recommendation && (
              <div className="mt-2.5 w-full bg-white border border-orange-300 rounded-xl p-3.5 shadow-xs space-y-2.5">
                <div className="flex items-center justify-between border-b border-orange-100 pb-2">
                  <div className="flex items-center gap-1.5 text-orange-900 font-bold text-xs">
                    <ShieldCheck className="w-4 h-4 text-orange-600" />
                    <span>MITIGATION ADVISORY ACTION</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                      HUMAN-IN-THE-LOOP
                    </span>
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-orange-100 text-orange-800 border border-orange-200">
                      Confidence: {msg.recommendation.confidencePercent}%
                    </span>
                  </div>
                </div>

                <div className="text-xs font-semibold text-slate-900">
                  {msg.recommendation.actionTitle}
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-600 bg-slate-50 p-2 rounded border border-slate-200">
                  <div>Qdrant Evidence: {msg.recommendation.evidenceCount} docs</div>
                  <div>Live Telemetry: {msg.recommendation.correlatedSignalsCount} sensors</div>
                </div>

                {msg.recommendation.approved ? (
                  <div className="p-2 rounded bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs font-semibold flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Mitigation Approved & Applied Successfully</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 pt-1">
                    <Button
                      variant="primary"
                      size="sm"
                      className="w-full bg-orange-600 hover:bg-orange-700 text-white"
                      onClick={() => approveRecommendation()}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                      Approve & Execute Mitigation
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Interim speech recognition feedback */}
        {interimText && (
          <div className="flex items-center gap-2 text-xs font-mono text-amber-700 p-2 bg-amber-50 rounded-lg border border-amber-200 animate-pulse">
            <Mic className="w-3.5 h-3.5 text-amber-600" />
            <span>&ldquo;{interimText}...&rdquo;</span>
          </div>
        )}

        {streaming && (
          <div className="flex items-center gap-2 text-xs font-mono text-orange-600 p-2 bg-orange-50 rounded-lg border border-orange-200">
            <span className="w-2 h-2 rounded-full bg-orange-500 animate-ping" />
            <span>Correlating plant telemetry, RAG memory & ML models...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Quick Operator Voice Queries ── */}
      <div className="px-3 py-2 bg-slate-100/70 border-t border-slate-200 flex items-center gap-1.5 overflow-x-auto text-[11px] font-mono">
        <span className="text-slate-400 shrink-0">Quick:</span>
        {quickPrompts.map((qp, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(qp.prompt)}
            className="px-2.5 py-1 rounded bg-white hover:bg-orange-50 hover:text-orange-700 hover:border-orange-300 border border-slate-200 text-slate-700 shrink-0 transition-colors shadow-2xs cursor-pointer"
          >
            {qp.label}
          </button>
        ))}
      </div>

      {/* ── Bottom Input & Voice Control ── */}
      <div className="p-3 border-t border-slate-200 bg-slate-50">
        <div className="flex items-center gap-2">
          {/* Voice Mic / Barge-In Button */}
          <button
            onClick={handleVoiceToggle}
            title={
              voiceState === 'speaking'
                ? 'Barge-In (Click to interrupt NOVA)'
                : voiceState === 'listening'
                ? 'Click to stop listening'
                : 'Click to speak to NOVA'
            }
            className={`p-2.5 rounded-xl border transition-all cursor-pointer shadow-xs ${
              voiceState === 'speaking'
                ? 'bg-red-500 hover:bg-red-600 text-white border-red-600 animate-pulse'
                : voiceState === 'listening'
                ? 'bg-amber-500 hover:bg-amber-600 text-white border-amber-600 ring-4 ring-amber-200'
                : 'bg-white hover:bg-orange-50 text-slate-700 border-slate-300 hover:border-orange-300'
            }`}
          >
            {voiceState === 'speaking' ? (
              <Square className="w-4 h-4 fill-white" />
            ) : voiceState === 'listening' ? (
              <MicOff className="w-4 h-4" />
            ) : (
              <Mic className="w-4 h-4 text-orange-600" />
            )}
          </button>

          {/* Text Input */}
          <input
            type="text"
            placeholder={
              voiceState === 'speaking'
                ? 'NOVA is speaking (press Mic to interrupt)...'
                : voiceState === 'listening'
                ? 'Listening to microphone...'
                : 'Ask NOVA or speak via microphone...'
            }
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            className="flex-1 bg-white border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-orange-500 font-sans shadow-2xs"
          />

          {/* Send button */}
          <button
            onClick={() => handleSend()}
            disabled={!inputVal.trim() && !interimText}
            className="p-2.5 rounded-xl bg-orange-500 hover:bg-orange-600 disabled:opacity-40 text-white cursor-pointer transition-colors shadow-xs"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mt-2 px-1">
          <span>Push-to-Talk · Barge-In Interrupt · Rime Mist-v3</span>
          <span className="text-emerald-600 font-semibold">● Audio Bridge Live</span>
        </div>
      </div>
    </div>
  )
}
