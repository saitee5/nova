import React, { useState, useRef, useEffect } from 'react'
import {
  X,
  Mic,
  MicOff,
  Send,
  CheckCircle2,
  Volume2,
  ShieldCheck,
} from 'lucide-react'
import { useRealtimeStore } from '../../stores/useRealtimeStore'
import { Button } from '../common/Button'

export const NovaCopilot: React.FC = () => {
  const isCopilotOpen = useRealtimeStore((s) => s.isCopilotOpen)
  const closeCopilot = useRealtimeStore((s) => s.closeCopilot)
  const messages = useRealtimeStore((s) => s.copilotMessages)
  const streaming = useRealtimeStore((s) => s.copilotStreaming)
  const voiceState = useRealtimeStore((s) => s.voiceState)
  const setVoiceState = useRealtimeStore((s) => s.setVoiceState)
  const sendMessage = useRealtimeStore((s) => s.sendUserMessage)
  const approveRecommendation = useRealtimeStore((s) => s.approveRecommendation)
  const selectedEquipmentId = useRealtimeStore((s) => s.selectedEquipmentId)
  const equipment = useRealtimeStore((s) =>
    selectedEquipmentId ? s.equipment[selectedEquipmentId] : null
  )

  const [inputVal, setInputVal] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isCopilotOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isCopilotOpen])

  if (!isCopilotOpen) return null

  const handleSend = () => {
    if (!inputVal.trim()) return
    sendMessage(inputVal)
    setInputVal('')
  }

  // Barge-In Voice State Machine
  const handleVoiceToggle = () => {
    if (voiceState === 'idle') {
      setVoiceState('listening')
      setTimeout(() => {
        setVoiceState('processing')
        setTimeout(() => {
          setVoiceState('speaking')
        }, 1200)
      }, 2500)
    } else if (voiceState === 'speaking') {
      // Barge-in triggered!
      setVoiceState('interrupted')
      setTimeout(() => {
        setVoiceState('listening')
      }, 400)
    } else {
      setVoiceState('idle')
    }
  }

  return (
    <div className="fixed top-0 right-0 bottom-0 w-full sm:w-[440px] bg-[#FAF3E1] border-l border-[#E8D7B0] shadow-2xl z-50 flex flex-col transition-all duration-300 animate-in slide-in-from-right font-sans">
      {/* ── Header ── */}
      <div className="p-4 border-b border-[#E8D7B0] bg-[#F5E7C6] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#2D0000] flex items-center justify-center text-[#FAF3E1] font-heading text-xs tracking-wider border border-[#4A0D0D]">
            NV
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-heading text-sm text-[#2D0000] tracking-tight">NOVA Copilot</span>
              <span className="px-1.5 py-0.2 text-[10px] font-mono font-bold bg-[#FAF3E1] text-[#2D0000] rounded border border-[#E8D7B0]">
                ACTIVE
              </span>
            </div>
            <p className="text-[11px] text-[#6B3530] font-subheading tracking-wider uppercase">
              Petrochemical Reasoning Engine
            </p>
          </div>
        </div>

        <button
          onClick={closeCopilot}
          className="p-1.5 rounded-md text-[#6B3530] hover:text-[#2D0000] hover:bg-[#FAF3E1] transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* ── Context Anchor Strip ── */}
      <div className="px-4 py-2 bg-[#F5E7C6]/60 border-b border-[#E8D7B0] flex items-center justify-between text-xs font-mono">
        <span className="text-[#6B3530]">
          Target Context:{' '}
          <strong className="text-[#2D0000] font-sans">
            {equipment ? `${equipment.tag} (${equipment.name})` : 'Whole Plant (Bay 1–5)'}
          </strong>
        </span>
        {equipment && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#FAF3E1] border border-[#E8D7B0] text-[#2D0000] font-bold">
            Risk: {equipment.riskScore}/100
          </span>
        )}
      </div>

      {/* ── Voice Status Indicator Bar ── */}
      <div className="px-4 py-2 bg-[#FAF3E1] border-b border-[#E8D7B0] flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              voiceState === 'listening'
                ? 'bg-amber-500 animate-ping'
                : voiceState === 'speaking'
                ? 'bg-emerald-500 animate-pulse'
                : voiceState === 'interrupted'
                ? 'bg-red-500'
                : 'bg-[#D9C394]'
            }`}
          />
          <span className="font-subheading text-xs text-[#6B3530] uppercase tracking-wider">
            Voice State: <strong className="text-[#2D0000]">{voiceState}</strong>
          </span>
        </div>

        {voiceState === 'speaking' && (
          <span className="text-[10px] font-mono text-[#FF6D1F] flex items-center gap-1 font-bold">
            <Volume2 className="w-3 h-3 animate-bounce" />
            Speaking (Barge-in ready)
          </span>
        )}
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
            <div className="flex items-center gap-1.5 text-[10px] text-[#6B3530] font-mono mb-1">
              <span className="font-bold">{msg.sender === 'user' ? 'Operator' : 'NOVA Core'}</span>
              <span>•</span>
              <span>{msg.timestamp}</span>
            </div>

            <div
              className={`p-3 rounded-lg max-w-[90%] leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-[#FF6D1F] text-white font-medium rounded-tr-none shadow-xs'
                  : 'bg-[#F5E7C6] border border-[#E8D7B0] text-[#2D0000] rounded-tl-none shadow-2xs font-sans'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
            </div>

            {/* Structured Recommendation Action Card */}
            {msg.recommendation && (
              <div className="mt-2.5 w-full bg-white border border-slate-200 rounded-lg p-3.5 shadow-none space-y-2.5">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <div className="flex items-center gap-1.5 text-slate-900 font-bold text-xs">
                    <ShieldCheck className="w-4 h-4 text-slate-700" />
                    <span>RECOMMENDED MITIGATION ACTION</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                    Confidence: {msg.recommendation.confidencePercent}%
                  </span>
                </div>

                <div className="text-xs font-semibold text-slate-900">
                  {msg.recommendation.actionTitle}
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-600 bg-slate-50 p-2 rounded border border-slate-200">
                  <div>Historical Matches: {msg.recommendation.evidenceCount} in Qdrant</div>
                  <div>Correlated Signals: {msg.recommendation.correlatedSignalsCount}</div>
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
                      className="w-full"
                      onClick={() => approveRecommendation()}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                      Approve & Execute Mitigation
                    </Button>
                    <Button variant="outline" size="sm">
                      Dismiss
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {streaming && (
          <div className="flex items-center gap-2 text-xs font-mono text-[#FF6D1F] p-2 bg-[#FFF7ED] rounded border border-[#FF6D1F]/40">
            <span className="w-2 h-2 rounded-full bg-[#FF6D1F] animate-ping" />
            <span>NOVA is correlating real-time plant telemetry...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Bottom Input & Voice Control ── */}
      <div className="p-3 border-t border-[#E8D7B0] bg-[#F5E7C6]">
        <div className="flex items-center gap-2">
          {/* Voice Mic Button */}
          <button
            onClick={handleVoiceToggle}
            title={
              voiceState === 'idle'
                ? 'Start Voice Session'
                : voiceState === 'speaking'
                ? 'Barge-In (Interrupt NOVA)'
                : 'Stop Voice'
            }
            className={`p-2.5 rounded-lg border transition-all cursor-pointer ${
              voiceState === 'speaking'
                ? 'bg-red-500 text-white border-red-600 animate-pulse'
                : voiceState === 'listening'
                ? 'bg-[#FF6D1F] text-white border-[#E05A12] animate-bounce'
                : 'bg-[#FAF3E1] text-[#2D0000] border-[#E8D7B0] hover:bg-white'
            }`}
          >
            {voiceState === 'idle' ? (
              <Mic className="w-4 h-4 text-[#FF6D1F]" />
            ) : (
              <MicOff className="w-4 h-4" />
            )}
          </button>

          {/* Text Input */}
          <input
            type="text"
            placeholder={
              voiceState === 'speaking'
                ? 'NOVA is speaking (press Mic to interrupt)...'
                : 'Ask NOVA (e.g., analyze furnace vibration)...'
            }
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            className="flex-1 bg-white border border-[#E8D7B0] rounded-lg px-3 py-2 text-xs text-[#2D0000] placeholder-[#6B3530]/60 focus:outline-none focus:border-[#FF6D1F] font-sans shadow-2xs"
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={!inputVal.trim()}
            className="p-2.5 rounded-lg bg-[#FF6D1F] hover:bg-[#E05A12] disabled:opacity-40 text-white cursor-pointer transition-colors shadow-xs"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-[#6B3530] mt-2 px-1">
          <span>Push-to-talk & Barge-in active</span>
          <span>Latency: 142ms</span>
        </div>
      </div>
    </div>
  )
}
