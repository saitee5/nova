import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface FurnaceProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Furnace: React.FC<FurnaceProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const radiantBoxRef = useRef<THREE.MeshStandardMaterial>(null)
  const stackRef = useRef<THREE.MeshStandardMaterial>(null)
  const heroRingRef = useRef<THREE.MeshBasicMaterial>(null)

  const isHeroAsset = equipment.id === 'F-201A'
  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (radiantBoxRef.current && isHighOrCritical) {
      const freq = riskTier === 'CRITICAL' ? 7 : 3.5
      const pulse = (Math.sin(state.clock.elapsedTime * freq) + 1) * 0.5
      radiantBoxRef.current.emissiveIntensity = 0.3 + pulse * (riskTier === 'CRITICAL' ? 1.0 : 0.5)
      if (stackRef.current) {
        stackRef.current.emissiveIntensity = 0.2 + pulse * 0.4
      }
    }
    // Subtle breathing glow for hero asset's ML halo
    if (heroRingRef.current) {
      heroRingRef.current.opacity = 0.35 + Math.sin(state.clock.elapsedTime * 2.5) * 0.15
    }
  })

  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000

  // Burner flame status map
  const flames = equipment.telemetry.burnerFlameStatus || {}

  return (
    <group
      ref={groupRef}
      position={equipment.position}
      onClick={(e) => {
        e.stopPropagation()
        onClick?.(e)
      }}
      onPointerOver={() => {
        document.body.style.cursor = 'pointer'
      }}
      onPointerOut={() => {
        document.body.style.cursor = 'auto'
      }}
    >
      {/* ── HERO ASSET ML BEACON / GROUND HALO ── */}
      {isHeroAsset && (
        <group position={[0, 0.08, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          {/* Outer Pulsing Cyan/Gold ML Monitoring Halo */}
          <mesh>
            <ringGeometry args={[4.8, 5.3, 48]} />
            <meshBasicMaterial
              ref={heroRingRef}
              color="#0284c7" // Tech Cyan / AI Monitor Glow
              side={THREE.DoubleSide}
              transparent
              opacity={0.4}
            />
          </mesh>
          {/* Inner Accent Ring */}
          <mesh>
            <ringGeometry args={[4.4, 4.55, 48]} />
            <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.6} />
          </mesh>
        </group>
      )}

      {/* Foundation Concrete Base */}
      <mesh position={[0, 0.25, 0]} receiveShadow>
        <boxGeometry args={[7.6, 0.5, 6.6]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.55, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[4.6, 5.1, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Burner Floor & Air Register Skids (Lower Hearth) */}
      <mesh position={[0, 0.8, 0]}>
        <boxGeometry args={[6.8, 0.6, 5.8]} />
        <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.6} />
      </mesh>

      {/* 4 Bottom Burner Nozzles */}
      {[
        { id: 'B-101', pos: [-2.2, 0.5, -1.8] },
        { id: 'B-102', pos: [2.2, 0.5, -1.8] },
        { id: 'B-103', pos: [-2.2, 0.5, 1.8] },
        { id: 'B-104', pos: [2.2, 0.5, 1.8] },
      ].map((b) => {
        const status = flames[b.id] || 'on'
        const color = status === 'fault' ? '#ef4444' : status === 'off' ? '#475569' : '#38bdf8'
        return (
          <group key={b.id} position={b.pos as [number, number, number]}>
            <mesh>
              <cylinderGeometry args={[0.3, 0.35, 0.4, 12]} />
              <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.3} />
            </mesh>
            {status !== 'off' && (
              <pointLight position={[0, -0.2, 0]} color={color} intensity={status === 'fault' ? 1.2 : 0.6} distance={2.5} />
            )}
          </group>
        )
      })}

      {/* Radiant Firebox (Lower, Wider Section) */}
      <mesh position={[0, 3.5, 0]} castShadow receiveShadow>
        <boxGeometry args={[6.4, 4.8, 5.4]} />
        <meshStandardMaterial
          ref={radiantBoxRef}
          color={isAlarm ? '#7f1d1d' : isHeroAsset ? '#334155' : '#475569'}
          metalness={0.6}
          roughness={0.4}
          emissive={emissiveColor}
          emissiveIntensity={isHighOrCritical ? 0.4 : 0}
        />
      </mesh>

      {/* External Structural Buckstays / Steel Columns */}
      {[-3.0, -1.0, 1.0, 3.0].map((x, idx) => (
        <React.Fragment key={idx}>
          <mesh position={[x, 3.5, 2.78]}>
            <boxGeometry args={[0.2, 5.0, 0.2]} />
            <meshStandardMaterial color="#0f172a" metalness={0.8} roughness={0.3} />
          </mesh>
          <mesh position={[x, 3.5, -2.78]}>
            <boxGeometry args={[0.2, 5.0, 0.2]} />
            <meshStandardMaterial color="#0f172a" metalness={0.8} roughness={0.3} />
          </mesh>
        </React.Fragment>
      ))}

      {/* Convection Section Transition Hood (Breeching) */}
      <mesh position={[0, 6.4, 0]} castShadow>
        <cylinderGeometry args={[2.2, 3.0, 1.2, 8]} />
        <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Upper Convection Section (Narrower Tube Bank Box) */}
      <mesh position={[0, 7.8, 0]} castShadow>
        <boxGeometry args={[4.0, 1.6, 3.4]} />
        <meshStandardMaterial color="#475569" metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Flue Gas Stack (Tall Thin Cylinder) */}
      <mesh ref={stackRef as any} position={[0, 12.8, 0]} castShadow>
        <cylinderGeometry args={[0.85, 1.15, 8.4, 18]} />
        <meshStandardMaterial
          ref={stackRef}
          color="#64748b"
          metalness={0.7}
          roughness={0.3}
          emissive={emissiveColor}
          emissiveIntensity={isHighOrCritical ? 0.2 : 0}
        />
      </mesh>

      {/* Stack Aircraft Warning Bands (Red / White) */}
      <mesh position={[0, 15.6, 0]}>
        <cylinderGeometry args={[0.88, 0.91, 0.9, 18]} />
        <meshStandardMaterial color="#dc2626" metalness={0.3} roughness={0.5} />
      </mesh>
      <mesh position={[0, 16.5, 0]}>
        <cylinderGeometry args={[0.86, 0.88, 0.9, 18]} />
        <meshStandardMaterial color="#f8fafc" metalness={0.3} roughness={0.5} />
      </mesh>

      {/* Continuous Access Walkway Platforms */}
      <mesh position={[0, 5.9, 0]}>
        <boxGeometry args={[7.0, 0.12, 6.0]} />
        <meshStandardMaterial color="#1e293b" metalness={0.7} roughness={0.4} />
      </mesh>
      <mesh position={[0, 8.7, 0]}>
        <boxGeometry args={[4.6, 0.1, 4.0]} />
        <meshStandardMaterial color="#1e293b" metalness={0.7} roughness={0.4} />
      </mesh>

      {/* Hero Asset Tag Plaque */}
      {isHeroAsset && (
        <mesh position={[0, 4.2, 2.76]}>
          <boxGeometry args={[1.8, 0.5, 0.08]} />
          <meshStandardMaterial color="#0284c7" emissive="#0284c7" emissiveIntensity={0.3} />
        </mesh>
      )}
    </group>
  )
}
