import { Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import heroHandsImg from '../assets/hero-hands.png'
import HeroSection from '../components/HeroSection'
import LOGO from '../assets/LOGO.png'
import { motion } from 'framer-motion'
import BackA from '../assets/BackA.png'

export default function HomePage() {
  return (
    <div style={{ background: '#fafaf5', minHeight: '100vh', overflowX: 'hidden' }}>
      <HomeNavbar />
      <HeroSection />
      <ProblemSection />
      <ApproachSection />
      <CapabilitiesSection />
      <CTASection />
      <HomeFooter />
    </div>
  )
}

function useScrollReveal() {
  const ref = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
        }
      },
      { threshold: 0.12 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  return { ref, isVisible }
}

function HomeNavbar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <nav
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        height: '86px',
        display: 'flex',
        alignItems: 'center',
        background: scrolled ? 'rgba(10, 13, 11, 0.75)' : 'rgba(10, 13, 11, 0.35)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '1455px',
          margin: '0 auto',
          padding: '0 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {/* NOVA LOGO */}
        <Link
          to="/"
          style={{
            display: 'flex',
            alignItems: 'center',
            textDecoration: 'none',
            flexShrink: 0,
          }}
        >
          <img
            src={LOGO}
            alt="NOVA"
            style={{
              width: '205px',
              height: 'auto',
              display: 'block',
            }}
          />
        </Link>

        {/* NAVIGATION */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '28px',
          }}
        >
          {[
            { label: 'OVERVIEW', href: '#product' },
            { label: 'APPROACH', href: '#approach' },
            { label: 'CAPABILITIES', href: '#capabilities' },
          ].map((item) => (
            <a
              key={item.label}
              href={item.href}
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '12px',
                fontWeight: 700,
                color: 'rgba(255,255,255,0.85)',
                textDecoration: 'none',
                letterSpacing: '0.12em',
                whiteSpace: 'nowrap',
                transition: 'color 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#c8f542';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'rgba(255,255,255,0.85)';
              }}
            >
              {item.label}
            </a>
          ))}

          {/* DIVIDER */}
          <div style={{ width: '1px', height: '18px', background: 'rgba(255,255,255,0.18)' }} />

          {/* FRONTEND PAGES NAVIGATION */}
          {[
            { label: 'COMMAND CENTER', to: '/command-center' },
            { label: '3D TWIN', to: '/digital-twin' },
            { label: 'ALERTS', to: '/alerts' },
            { label: 'ANALYTICS', to: '/analytics' },
          ].map((item) => (
            <Link
              key={item.label}
              to={item.to}
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '12px',
                fontWeight: 700,
                color: 'rgba(255,255,255,0.85)',
                textDecoration: 'none',
                letterSpacing: '0.12em',
                whiteSpace: 'nowrap',
                transition: 'color 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#c8f542';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'rgba(255,255,255,0.85)';
              }}
            >
              {item.label}
            </Link>
          ))}

          {/* LIVE STATUS */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              height: '22px',
              padding: '0 8px',
              borderRadius: '4px',
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.25)',
            }}
          >
            <div
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                background: '#c8f542',
                boxShadow: '0 0 7px rgba(200,245,66,0.8)',
                animation: 'pulse-ring 2s ease-in-out infinite',
              }}
            />

            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '11px',
                fontWeight: 700,
                color: '#fff',
                letterSpacing: '0.1em',
                lineHeight: 1,
              }}
            >
              LIVE
            </span>
          </div>

          {/* LAUNCH PLATFORM CTA */}
          <Link
            to="/command-center"
            style={{
              fontFamily: "'Titillium Web', sans-serif",
              fontSize: '12px',
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              background: '#4a6741',
              color: '#ffffff',
              padding: '8px 18px',
              borderRadius: '3px',
              clipPath: 'polygon(0 0, 92% 0, 100% 100%, 0% 100%)',
              textDecoration: 'none',
              transition: 'all 0.25s ease',
              whiteSpace: 'nowrap',
              boxShadow: '0 2px 10px rgba(74,103,65,0.4)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#587a4d'
              e.currentTarget.style.transform = 'translateY(-1px)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#4a6741'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            LAUNCH APP
          </Link>
        </div>
      </div>
    </nav>
  )
}

export function HeroBlock() {
  return (
    <section id="product" style={{
      position: 'relative',
      minHeight: '100vh',
      width: '100vw',
      display: 'flex',
      alignItems: 'center',
      paddingTop: '64px',
      overflow: 'hidden',
      background: 'linear-gradient(110deg, #161816 0%, #2a2e2a 45%, #6a706a 85%, #888e88 100%)',
    }}>
      <img
        src={heroHandsImg}
        alt="Robot and Human Hands Touching — NOVA AI Safety Intelligence"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: 'center center',
          opacity: 0.9,
          filter: 'contrast(1.12) brightness(0.9) grayscale(100%)',
          zIndex: 1,
          pointerEvents: 'none',
        }}
      />

      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(circle at 85% 25%, rgba(220,225,220,0.3) 0%, transparent 55%), linear-gradient(90deg, rgba(14,16,14,0.65) 0%, rgba(20,24,20,0.42) 40%, rgba(130,136,130,0.1) 85%, rgba(160,165,160,0.2) 100%)',
        zIndex: 2,
        pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)',
        backgroundSize: '80px 80px',
        zIndex: 2,
        pointerEvents: 'none',
      }} />

      <div style={{
        maxWidth: '1280px',
        width: '100%',
        margin: '0 auto',
        padding: '0 40px',
        position: 'relative',
        zIndex: 3,
      }}>
        <div style={{ maxWidth: '620px', animation: 'fade-up 0.8s ease both' }}>
          <h1 style={{
            fontFamily: "'Bebas Neue', sans-serif",
            fontSize: 'clamp(2.4rem, 4.2vw, 4.2rem)',
            lineHeight: 0.98,
            letterSpacing: '0.04em',
            color: '#ffffff',
            marginBottom: '20px',
            textShadow: '0 4px 20px rgba(0,0,0,0.85), 0 1px 4px rgba(0,0,0,0.9)',
          }}>
            COMPOUND RISK,
            <span style={{ display: 'block' }}>CAUGHT BEFORE IT</span>
            <span style={{ display: 'block' }}>COMPOUNDS.</span>
          </h1>

          <p style={{
            fontFamily: "'Titillium Web', sans-serif",
            fontSize: '0.95rem',
            fontWeight: 400,
            lineHeight: 1.55,
            color: 'rgba(255,255,255,0.95)',
            marginBottom: '32px',
            maxWidth: '520px',
            textShadow: '0 2px 12px rgba(0,0,0,0.9), 0 1px 3px rgba(0,0,0,0.95)',
          }}>
            Detect unrelated signals across sensors and systems — permitting, operations, CCTV, behaviour — and fuse them into actionable compound risk in real time.
          </p>

          <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
            <Link
              to="/command-center"
              style={{
                fontFamily: "'Titillium Web', sans-serif",
                fontWeight: 700,
                fontSize: '0.8rem',
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                background: '#4a6741',
                color: '#ffffff',
                padding: '14px 32px',
                borderRadius: '3px',
                clipPath: 'polygon(0 0, 92% 0, 100% 100%, 0% 100%)',
                textDecoration: 'none',
                transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
                display: 'inline-flex',
                alignItems: 'center',
                boxShadow: '0 4px 16px rgba(74,103,65,0.4)',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = '#587a4d'
                e.currentTarget.style.transform = 'scale(1.05) translateY(-4px)'
                e.currentTarget.style.boxShadow = '0 8px 24px rgba(74,103,65,0.6)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = '#4a6741'
                e.currentTarget.style.transform = 'scale(1) translateY(0)'
                e.currentTarget.style.boxShadow = '0 4px 16px rgba(74,103,65,0.4)'
              }}
            >
              SEE IT IN ACTION
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}


function ProblemSection() {
  const isolatedSignals = [
    {
      title: 'GAS SENSOR',
      reading: '+8% H₂S Above Baseline',
      verdict: 'Individually Unremarkable',
      desc: 'Not high enough to breach a single-sensor SCADA threshold alarm.',
      tag: '01 / SENSOR SCADA',
    },
    {
      title: 'PERMIT TO WORK',
      reading: 'Hot-Work Welding Active',
      verdict: 'Routine Paperwork',
      desc: 'Authorized permit PTW-0441 active in Bay 3 compressor zone.',
      tag: '02 / PERMIT SYSTEM',
    },
    {
      title: 'MAINTENANCE LOG',
      reading: 'Thermal Drift Flag',
      verdict: 'Logbook Footnote',
      desc: 'Compressor C-14 seal inspection logged two hours prior.',
      tag: '03 / CMMS LOG',
    },
    {
      title: 'SHIFT ROSTER',
      reading: 'Handover in 20 Mins',
      verdict: 'Scheduling Event',
      desc: 'Supervisory shift changeover scheduled across facility.',
      tag: '04 / SHIFT ROSTER',
    },
  ]

  return (
    <section
      id="problem"
      style={{
        position: 'relative',
        padding: '120px 0',
        color: '#F3F0E6',
        overflow: 'hidden',

        /* BACKGROUND IMAGE */
        backgroundImage: `
          linear-gradient(
            rgba(10, 17, 10, 0.82),
            rgba(10, 17, 10, 0.92)
          ),
          url('${BackA}')
        `,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
      }}
    >

      {/* SUBTLE GRID OVERLAY */}


      <div
        style={{
          position: 'relative',
          zIndex: 1,
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 40px',
        }}
      >

        {/* SECTION HEADER */}
        <motion.div
          initial={{
            opacity: 0,
            y: 50,
          }}
          whileInView={{
            opacity: 1,
            y: 0,
          }}
          viewport={{
            once: true,
            amount: 0.25,
          }}
          transition={{
            duration: 0.7,
            ease: [0.16, 1, 0.3, 1],
          }}
          style={{
            marginBottom: '70px',
          }}
        >

          {/* EYEBROW */}
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.65rem',
              letterSpacing: '0.14em',
              color: '#B7C9A8',
              fontWeight: 700,
              textTransform: 'uppercase',
              marginBottom: '12px',
            }}
          >
            THE SYSTEMIC INDUSTRIAL GAP
          </div>

          {/* HEADING */}
          <h2
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              fontSize: 'clamp(3rem, 6vw, 5.5rem)',
              color: '#F3F0E6',
              lineHeight: 0.9,
              maxWidth: '800px',
              margin: 0,
              letterSpacing: '0.01em',
            }}
          >
            Industrial Disasters
            <br />
            Don't Start With
            <br />
            <span style={{ color: '#A8B89A' }}>
              Single Alarms
            </span>
          </h2>

          {/* DESCRIPTION */}
          <p
            style={{
              fontFamily: "'Titillium Web', sans-serif",
              fontSize: '1rem',
              fontWeight: 400,
              color: 'rgba(243,240,230,0.72)',
              lineHeight: 1.65,
              maxWidth: '800px',
              marginTop: '24px',
              marginBottom: 0,
            }}
          >
            DGFASLI recorded over 6,500 fatal workplace accidents in India in
            FY2023. In January 2025 at the Visakhapatnam Steel Plant, eight
            workers died in a coke oven explosion despite functioning gas
            detectors, permit controls, and SCADA. The warning signals existed
            — but no intelligence connected them in time. A FICCI survey found
            that over 60 percent of industrial facilities rely on manual
            handoffs between isolated safety tools.
          </p>

        </motion.div>


        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '20px',
          }}
        >
          {isolatedSignals.map((sig, idx) => (
            <motion.div
              key={sig.title}
              initial={{
                opacity: 0,
                y: 50,
              }}
              whileInView={{
                opacity: 1,
                y: 0,
              }}
              viewport={{
                once: true,
                amount: 0.2,
              }}
              transition={{
                duration: 0.6,
                delay: idx * 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}
              whileHover={{
                y: -6,
                transition: {
                  duration: 0.25,
                  ease: 'easeOut',
                },
              }}
              style={{
                position: 'relative',

                /* GLASS EFFECT */
                background: 'rgba(255, 255, 255, 0.07)',
                backdropFilter: 'blur(5px)',
                WebkitBackdropFilter: 'blur(5px)',

                /* VERY SUBTLE BORDER */
                border: '1px solid rgba(255, 255, 255, 0.18)',

                borderRadius: '14px',

                padding: '30px',

                minHeight: '190px',

                /* SOFT GLASS SHADOW */
                boxShadow: `
          0 10px 35px rgba(0, 0, 0, 0.18),
          inset 0 1px 0 rgba(255, 255, 255, 0.12)
        `,

                overflow: 'hidden',
              }}
            >

              {/* SUBTLE GREEN GLOW */}
              <div
                style={{
                  position: 'absolute',
                  top: '-80px',
                  right: '-80px',
                  width: '180px',
                  height: '180px',
                  borderRadius: '50%',
                  background: 'rgba(145, 165, 131, 0.08)',
                  filter: 'blur(45px)',
                  pointerEvents: 'none',
                }}
              />

              {/* TOP ROW */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '18px',
                }}
              >

                {/* NUMBER / TAG */}
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '0.55rem',
                    color: '#A8B89A',
                    letterSpacing: '0.12em',
                    fontWeight: 700,
                  }}
                >
                  {sig.tag}
                </div>



              </div>


              {/* TITLE */}
              <h3
                style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  fontSize: '1.6rem',
                  color: '#F3F0E6',
                  letterSpacing: '0.04em',
                  margin: '0 0 10px 0',
                  lineHeight: 1,
                }}
              >
                {sig.title}
              </h3>


              {/* READING */}
              <div
                style={{
                  fontFamily: "'Titillium Web', sans-serif",
                  fontSize: '1rem',
                  fontWeight: 700,
                  color: '#D6C18A',
                  marginBottom: '4px',
                }}
              >
                {sig.reading}
              </div>


              {/* VERDICT */}
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '0.55rem',
                  color: 'rgba(243, 240, 230, 0.55)',
                  letterSpacing: '0.03em',
                  marginBottom: '12px',
                }}
              >
                VERDICT: {sig.verdict}
              </div>


              {/* DESCRIPTION */}
              <p
                style={{
                  fontFamily: "'Titillium Web', sans-serif",
                  fontSize: '0.78rem',
                  fontWeight: 400,
                  color: 'rgba(243, 240, 230, 0.62)',
                  lineHeight: 1.5,
                  margin: 0,
                  maxWidth: '500px',
                }}
              >
                {sig.desc}
              </p>

            </motion.div>
          ))}
        </div>


        {/* BOTTOM STATEMENT */}
        <motion.div
          initial={{
            opacity: 0,
            y: 30,
          }}
          whileInView={{
            opacity: 1,
            y: 0,
          }}
          viewport={{
            once: true,
            amount: 0.3,
          }}
          transition={{
            duration: 0.7,
            delay: 0.2,
          }}
          style={{
            marginTop: '55px',
            display: 'flex',
            alignItems: 'center',
            gap: '18px',
          }}
        >

          <div
            style={{
              width: '42px',
              height: '2px',
              background: '#A8B89A',
            }}
          />

          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.65rem',
              letterSpacing: '0.08em',
              color: 'rgba(243,240,230,0.65)',
              textTransform: 'uppercase',
            }}
          >
            The signals exist. The connection doesn't.
          </div>

        </motion.div>

      </div>
    </section>
  )
}

function ApproachSection() {
  const steps = [
    {
      num: '01',
      title: 'DETECT & CONTEXTUALIZE',
      desc: 'Continuous stream ingestion across SCADA, permits, CCTV, and maintenance logs inside a rolling time window per bay.',
    },
    {
      num: '02',
      title: 'RETRIEVE MEMORY',
      desc: 'Searching Qdrant vector memory for matching historical near-misses and organizational precedents.',
    },
    {
      num: '03',
      title: 'REASON & EXPLAIN',
      desc: 'Computing compound risk via auditable, deterministic arithmetic and structuring transparent evidence chains.',
    },
    {
      num: '04',
      title: 'PROACTIVE VOICE RECOMMENDATION',
      desc: 'Initiating hands-free voice calls to safety officers structured as state → evidence → ask.',
    },
    {
      num: '05',
      title: 'AUTHORIZE & ACT',
      desc: 'Single human confirmation gate before executing typed safety tools with immutable audit logging.',
    },
    {
      num: '06',
      title: 'COMPOUNDING MEMORY',
      desc: 'Embedding resolved incidents back into Qdrant memory so the next incident is caught faster.',
    },
  ]

  return (
    <section
      id="approach"
      style={{
        background: '#F3F0E6',
        padding: '110px 0',
        color: '#4a6741',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 40px',
        }}
      >

        {/* SECTION HEADER */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{
            once: true,
            amount: 0.25,
          }}
          transition={{
            duration: 0.7,
            ease: [0.16, 1, 0.3, 1],
          }}
          style={{
            marginBottom: '55px',
          }}
        >
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.65rem',
              letterSpacing: '0.14em',
              color: '#4a6741',
              fontWeight: 700,
              textTransform: 'uppercase',
              marginBottom: '10px',
            }}
          >
            THE STANDING AGENTIC PIPELINE
          </div>

          <h2
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              fontSize: 'clamp(2.8rem, 5vw, 4.5rem)',
              color: '#0b0f0aff',
              lineHeight: 0.9,
              margin: 0,
              letterSpacing: '0.01em',
            }}
          >
            How Nova Reasons
            <br />
            and Operates
          </h2>

          <p
            style={{
              fontFamily: "'Titillium Web', sans-serif",
              fontSize: '1rem',
              fontWeight: 400,
              color: 'rgba(74,103,65,0.75)',
              maxWidth: '640px',
              marginTop: '18px',
              lineHeight: 1.6,
            }}
          >
            NOVA runs a continuous autonomous loop over live operational data.
            It speaks up the moment an otherwise invisible combination of facts
            becomes dangerous.
          </p>
        </motion.div>

        {/* 6 CARDS */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '20px',
          }}
        >
          {steps.map((step, idx) => (
            <motion.div
              key={step.num}

              /* POP-UP START STATE */
              initial={{
                opacity: 0,
                y: 70,
                scale: 0.94,
              }}

              /* WHEN USER SCROLLS TO IT */
              whileInView={{
                opacity: 1,
                y: 0,
                scale: 1,
              }}

              viewport={{
                once: true,
                amount: 0.2,
              }}

              transition={{
                duration: 0.65,
                delay: idx * 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}

              whileHover={{
                y: -8,
                scale: 1.015,
                transition: {
                  duration: 0.25,
                  ease: 'easeOut',
                },
              }}

              style={{
                position: 'relative',
                background: '#E8E5D8',
                border: '1px solid rgba(74,103,65,0.28)',
                borderTop: '3px solid #4a6741',
                borderRadius: '8px',
                padding: '28px 24px',
                minHeight: '185px',
                boxShadow: '0 8px 25px rgba(74,103,65,0.08)',
                cursor: 'default',
                transition: 'box-shadow 0.3s ease',
              }}
            >

              {/* STEP NUMBER */}
              <div
                style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  fontSize: '2.8rem',
                  color: '#4a6741',
                  lineHeight: 1,
                  marginBottom: '8px',
                }}
              >
                {step.num}
              </div>

              {/* TITLE */}
              <h3
                style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  fontSize: '1.35rem',
                  color: '#4a6741',
                  letterSpacing: '0.04em',
                  margin: '0 0 10px 0',
                  lineHeight: 1,
                }}
              >
                {step.title}
              </h3>

              {/* DESCRIPTION */}
              <p
                style={{
                  fontFamily: "'Titillium Web', sans-serif",
                  fontSize: '0.82rem',
                  fontWeight: 400,
                  color: 'rgba(40,55,38,0.72)',
                  lineHeight: 1.55,
                  margin: 0,
                }}
              >
                {step.desc}
              </p>

              {/* LITTLE GREEN CORNER */}
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 0,
                  width: '18px',
                  height: '18px',
                  borderTop: '3px solid #4a6741',
                  borderRight: '3px solid #4a6741',
                  borderRadius: '0 6px 0 0',
                  opacity: 0.5,
                }}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}



function CapabilitiesSection() {
  const capabilities = [
    {
      title: 'COMPOUND-RISK REASONING',
      why: 'Standing correlation loop that initiates contact proactively, not a chatbot waiting to be asked.',
    },
    {
      title: 'TEMPORAL CORRELATION',
      why: 'Multi-signal stateful reasoning across rolling time windows, not single-snapshot retrieval calls.',
    },
    {
      title: 'DECISION-DRIVING RETRIEVAL',
      why: 'Qdrant vector similarity score directly inputs into compound risk arithmetic, altering decision tiers.',
    },
    {
      title: 'COMPOUNDING ORGANIZATIONAL MEMORY',
      why: 'Every resolved incident writes back into memory, strengthening subsequent detections in real time.',
    },
    {
      title: 'INTERRUPTION-SAFE VOICE (BARGE-IN)',
      why: 'Native interruption-state stack preventing conversation loss when interrupted mid-sentence.',
    },
    {
      title: 'DETERMINISTIC SAFETY ARCHITECTURE',
      why: 'Strict human authorization gate — the reasoning layer proposes, it never executes unilaterally.',
    },
  ]

  return (
    <section
      id="capabilities"
      style={{
        background: '#F3F0E6',
        padding: '110px 0',
        color: '#4a6741',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 40px',
        }}
      >

        {/* SECTION HEADER */}
        <motion.div
          initial={{
            opacity: 0,
            y: 50,
          }}
          whileInView={{
            opacity: 1,
            y: 0,
          }}
          viewport={{
            once: true,
            amount: 0.25,
          }}
          transition={{
            duration: 0.7,
            ease: [0.16, 1, 0.3, 1],
          }}
          style={{
            marginBottom: '55px',
          }}
        >
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.65rem',
              letterSpacing: '0.14em',
              color: '#060805ff',
              fontWeight: 700,
              textTransform: 'uppercase',
              marginBottom: '10px',
            }}
          >
            CAPABILITIES & ADVANTAGES
          </div>

          <h2
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              fontSize: 'clamp(2.8rem, 5vw, 4.5rem)',
              color: '#0b0e0bff',
              lineHeight: 0.9,
              maxWidth: '800px',
              margin: 0,
              letterSpacing: '0.01em',
            }}
          >
            Why Generic Chatbots
            <br />
            & Dashboards Fail
          </h2>

          <p
            style={{
              fontFamily: "'Titillium Web', sans-serif",
              fontSize: '1rem',
              fontWeight: 400,
              color: 'rgba(74,103,65,0.75)',
              lineHeight: 1.6,
              maxWidth: '680px',
              marginTop: '20px',
            }}
          >
            Workers in hazardous industrial zones wear PPE and operate heavy
            machinery. They cannot safely stop to read screens or type prompts
            into chatbots.
          </p>
        </motion.div>

        {/* CAPABILITY CARDS */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '20px',
          }}
        >
          {capabilities.map((cap, idx) => (
            <motion.div
              key={cap.title}

              // Initial hidden state
              initial={{
                opacity: 0,
                y: 70,
                scale: 0.92,
              }}

              // Pop into view
              whileInView={{
                opacity: 1,
                y: 0,
                scale: 1,
              }}

              viewport={{
                once: true,
                amount: 0.2,
              }}

              // Stagger cards
              transition={{
                duration: 0.65,
                delay: idx * 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}

              // Hover effect
              whileHover={{
                y: -8,
                scale: 1.02,
                transition: {
                  duration: 0.25,
                  ease: 'easeOut',
                },
              }}

              style={{
                position: 'relative',
                background: '#E8E5D8',
                border: '1px solid rgba(74,103,65,0.25)',
                borderTop: '3px solid #4a6741',
                borderRadius: '8px',
                padding: '28px 24px',
                minHeight: '155px',
                boxShadow: '0 8px 25px rgba(74,103,65,0.07)',
                cursor: 'default',
              }}
            >

              {/* TITLE */}
              <h3
                style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  fontSize: '1.4rem',
                  color: '#4a6741',
                  letterSpacing: '0.04em',
                  lineHeight: 1,
                  margin: '0 0 12px 0',
                }}
              >
                {cap.title}
              </h3>

              {/* DESCRIPTION */}
              <p
                style={{
                  fontFamily: "'Titillium Web', sans-serif",
                  fontSize: '0.82rem',
                  fontWeight: 400,
                  color: 'rgba(40,55,38,0.72)',
                  lineHeight: 1.55,
                  margin: 0,
                }}
              >
                {cap.why}
              </p>

              {/* CORNER DETAIL */}
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 0,
                  width: '18px',
                  height: '18px',
                  borderTop: '3px solid #4a6741',
                  borderRight: '3px solid #4a6741',
                  borderRadius: '0 6px 0 0',
                  opacity: 0.45,
                }}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

function CTASection() {
  const { ref, isVisible } = useScrollReveal()

  return (
    <section ref={ref} style={{
      background: 'linear-gradient(135deg, #141c14 0%, #080c08 100%)',
      padding: '80px 0',
      color: '#ffffff',
      borderTop: '1px solid rgba(200,245,66,0.2)',
      opacity: isVisible ? 1 : 0,
      transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
      transition: 'all 0.7s cubic-bezier(0.16, 1, 0.3, 1)',
    }}>
      <div style={{
        maxWidth: '800px',
        margin: '0 auto',
        padding: '0 40px',
        textAlign: 'center',
      }}>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.6rem',
          letterSpacing: '0.14em',
          color: '#c8f542',
          fontWeight: 700,
          textTransform: 'uppercase',
          marginBottom: '10px',
        }}>
          EXPERIENCE AGENT-PILOTED SAFETY
        </div>
        <h2 style={{
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: 'clamp(2.4rem, 4vw, 3.6rem)',
          color: '#ffffff',
          lineHeight: 0.95,
          marginBottom: '16px',
        }}>
          Experience Nova in Action
        </h2>
        <p style={{
          fontFamily: "'Titillium Web', sans-serif",
          fontSize: '0.95rem',
          fontWeight: 300,
          color: 'rgba(255,255,255,0.7)',
          lineHeight: 1.55,
          marginBottom: '32px',
        }}>
          Select Scripted Demo Mode to experience the full 6-phase detection-to-resolution sequence, or Enter Live Simulation to converse with Nova against an unscripted telemetry stream.
        </p>

        <div style={{ display: 'flex', gap: '16px', justifyContent: 'center' }}>
          <Link
            to="/command-center"
            style={{
              fontFamily: "'Titillium Web', sans-serif",
              fontWeight: 700,
              fontSize: '0.8rem',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              background: '#4a6741',
              color: '#ffffff',
              padding: '14px 32px',
              borderRadius: '3px',
              clipPath: 'polygon(0 0, 92% 0, 100% 100%, 0% 100%)',
              textDecoration: 'none',
              transition: 'all 0.25s ease',
              boxShadow: '0 4px 16px rgba(74,103,65,0.4)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = '#587a4d'
              e.currentTarget.style.transform = 'translateY(-2px)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = '#4a6741'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            SEE IT IN ACTION
          </Link>
        </div>
      </div>
    </section>
  )
}

function HomeFooter() {
  const footerSections = [
    {
      title: 'PLATFORM',
      links: [
        { name: 'Command Center', path: '/command-center' },
        { name: '3D Digital Twin', path: '/digital-twin' },
        { name: 'Alerts & Incidents', path: '/alerts' },
      ],
    },
    {
      title: 'INTELLIGENCE',
      links: [
        { name: 'Risk Analytics', path: '/analytics' },
        { name: 'Equipment Explorer', path: '/equipment' },
        { name: 'Historical Intelligence', path: '/history' },
        { name: 'Decision Engine', path: '/command-center' },
      ],
    },
    {
      title: 'SYSTEM',
      links: [
        { name: 'Petrochemical Complex', path: '/command-center' },
        { name: 'Telemetry Stream (50Hz)', path: '/command-center' },
        { name: 'Copilot Assistant', path: '/command-center' },
        { name: 'Compliance & Safety', path: '#approach' },
      ],
    },
  ]

  return (
    <footer id="contact" style={{
      background: '#060a06',
      borderTop: '1px solid rgba(255,255,255,0.08)',
      padding: '50px 0 24px',
      color: 'rgba(255,255,255,0.6)',
    }}>
      <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 40px' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr 1fr 1fr',
          gap: '36px',
          paddingBottom: '36px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          marginBottom: '28px',
        }}>
          <div>
            <div style={{
              fontFamily: "'Bebas Neue', sans-serif",
              fontSize: '1.6rem',
              color: '#ffffff',
              letterSpacing: '0.08em',
              marginBottom: '6px',
            }}>
              NOVA
            </div>
            <p style={{
              fontFamily: "'Titillium Web', sans-serif",
              fontSize: '0.75rem',
              fontWeight: 300,
              color: 'rgba(255,255,255,0.45)',
              lineHeight: 1.5,
              maxWidth: '280px',
            }}>
              Agentic industrial safety intelligence system fusing gas sensors, permit logs, maintenance records, and CCTV into compound risk intelligence.
            </p>
          </div>

          {footerSections.map(col => (
            <div key={col.title}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '0.55rem',
                fontWeight: 700,
                color: '#c8f542',
                letterSpacing: '0.12em',
                marginBottom: '12px',
              }}>
                {col.title}
              </div>
              {col.links.map(l => (
                <div key={l.name} style={{ marginBottom: '6px' }}>
                  {l.path.startsWith('/') ? (
                    <Link
                      to={l.path}
                      style={{
                        fontFamily: "'Titillium Web', sans-serif",
                        fontSize: '0.72rem',
                        fontWeight: 300,
                        color: 'rgba(255,255,255,0.65)',
                        textDecoration: 'none',
                        transition: 'color 0.2s ease',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#c8f542' }}
                      onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.65)' }}
                    >
                      {l.name}
                    </Link>
                  ) : (
                    <a
                      href={l.path}
                      style={{
                        fontFamily: "'Titillium Web', sans-serif",
                        fontSize: '0.72rem',
                        fontWeight: 300,
                        color: 'rgba(255,255,255,0.5)',
                        textDecoration: 'none',
                        transition: 'color 0.2s ease',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#c8f542' }}
                      onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.5)' }}
                    >
                      {l.name}
                    </a>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>

        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '0.52rem',
            color: 'rgba(255,255,255,0.3)',
          }}>
            Built by team .bin under VoxForge track @ StarForge 2026
          </span>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: 5,
              height: 5,
              borderRadius: '50%',
              background: '#c8f542',
              boxShadow: '0 0 5px #c8f542',
            }} />
            <span style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.52rem',
              color: '#c8f542',
              letterSpacing: '0.1em',
              fontWeight: 700,
            }}>
              SYSTEM OPERATIONAL
            </span>
          </div>
        </div>
      </div>
    </footer>
  )
}
