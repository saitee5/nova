import { useState, useEffect } from 'react'
import { useThemeStore } from '../store/useThemeStore'
import { Menu, X } from 'lucide-react'
import LOGO from "../assets/LOGO.png"

export default function Navbar() {
  const { theme, toggle } = useThemeStore()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const links = [
    { label: '3D Live Twin', href: '/twin' },
    { label: 'Product', href: '#product' },
    { label: 'Approach', href: '#approach' },
    { label: 'Capabilities', href: '#capabilities' },
    { label: 'Contact', href: '#contact' },
  ]

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-[100] mb-20px transition-all duration-350 ${scrolled
        ? 'bg-[var(--nav-bg)] backdrop-blur-xl border-b border-[var(--border)]'
        : 'bg-transparent border-b border-transparent'
        }`}
    >
      <div className="container flex items-center h-16 gap-8" style={{ marginBottom: '8px' }}>
        <a href="/" className="flex items-center gap-2 no-underline shrink-0">
          <img src={LOGO} alt="Logo" className='w-50 h-20 mt-10 ml-10' />
        </a>

        <div className="hidden md:flex items-center gap-8 ml-auto">
          {links.map((l) => (
            <a key={l.label} href={l.href} className="nav-link" style={{ color: '#FFFFFF' }}>
              {l.label}
            </a>
          ))}

          <div
            className="flex items-center gap-1.5 px-3 py-1 rounded-sm"
            style={{ border: '1px solid rgba(255,255,255,0.4)', background: 'rgba(255,255,255,0.08)' }}
          >
            <span
              className="w-1.75 h-1.75 rounded-full inline-block animate-pulse-ring"
              style={{ background: '#FFFFFF' }}
            />
            <span className="font-mono text-[0.65rem] font-bold tracking-[0.12em]" style={{ color: '#FFFFFF' }}>
              LIVE
            </span>
          </div>

          <ThemeToggle theme={theme} toggle={toggle} />
        </div>

        <div className="flex md:hidden items-center gap-4 ml-auto">
          <ThemeToggle theme={theme} toggle={toggle} />
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="bg-transparent border-0 cursor-pointer p-1"
            style={{ color: '#FFFFFF' }}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="bg-[var(--nav-bg)] backdrop-blur-xl border-t border-[var(--border)] px-8 py-4 flex flex-col gap-4">
          {links.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="nav-link text-sm py-2"
              style={{ color: '#FFFFFF' }}
              onClick={() => setMobileOpen(false)}
            >
              {l.label}
            </a>
          ))}
        </div>
      )}
    </nav>
  )
}

export function VIGILLogo() {
  const color = '#FFFFFF'

  return (
    <svg width="165" height="48" viewBox="0 0 236 68" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* N */}
      <path d="M 14 44 V 10 L 44 44 V 10" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* O (Audio Waveform Ring) */}
      <g>
        {/* Top & Bottom Arcs */}
        <path d="M 70 23 A 17 17 0 0 1 102 23" stroke={color} strokeWidth="2" fill="none" strokeLinecap="round" />
        <path d="M 70 31 A 17 17 0 0 0 102 31" stroke={color} strokeWidth="2" fill="none" strokeLinecap="round" />

        {/* Equalizer Waveform Bars */}
        <rect x="85" y="15" width="2.2" height="24" rx="1.1" fill={color} />
        <rect x="80" y="19" width="2.2" height="16" rx="1.1" fill={color} opacity="0.9" />
        <rect x="90" y="19" width="2.2" height="16" rx="1.1" fill={color} opacity="0.9" />
        <rect x="75" y="22" width="2.2" height="10" rx="1.1" fill={color} opacity="0.7" />
        <rect x="95" y="22" width="2.2" height="10" rx="1.1" fill={color} opacity="0.7" />

        {/* Side dots */}
        <circle cx="67" cy="27" r="1.2" fill={color} opacity="0.6" />
        <circle cx="105" cy="27" r="1.2" fill={color} opacity="0.6" />
      </g>

      {/* V */}
      <path d="M 126 10 L 144 44 L 162 10" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* A (with Sparkle) */}
      <g>
        <path d="M 182 44 L 200 10 L 218 44" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {/* Star sparkle inside A */}
        <path d="M 200 27 Q 200 32 205 32 Q 200 32 200 37 Q 200 32 195 32 Q 200 32 200 27 Z" fill={color} />
      </g>

      {/* Center Divider Line & Sparkle */}
      <line x1="14" y1="52" x2="110" y2="52" stroke={color} strokeWidth="0.8" opacity="0.4" />
      <line x1="126" y1="52" x2="218" y2="52" stroke={color} strokeWidth="0.8" opacity="0.4" />
      <path d="M 118 47 Q 118 52 123 52 Q 118 52 118 57 Q 118 52 113 52 Q 118 52 118 47 Z" fill={color} opacity="0.8" />

      {/* Tagline */}
      <text
        x="116"
        y="64"
        textAnchor="middle"
        fontFamily="'Titillium Web', 'Inter', sans-serif"
        fontSize="6.5"
        fontWeight="600"
        letterSpacing="1.4"
        fill={color}
        opacity="0.85"
      >
        THE VOICE THAT NOTICES WHAT NO SINGLE SENSOR CAN
      </text>
    </svg>
  )
}

export const NOVALogo = VIGILLogo

function ThemeToggle({ theme, toggle }: { theme: string; toggle: () => void }) {
  return (
    <button
      onClick={toggle}
      className="theme-toggle"
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{ display: 'flex', alignItems: 'center' }}
    />
  )
}
