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
  })

  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000

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
      {/* Foundation Base */}
      <mesh position={[0, 0.25, 0]} receiveShadow>
        <boxGeometry args={[7.2, 0.5, 6.2]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.55, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[4.5, 5.0, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Burner Floor & Air Register Skids */}
      <mesh position={[0, 0.8, 0]}>
        <boxGeometry args={[6.4, 0.6, 5.4]} />
        <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.6} />
      </mesh>

      {/* Radiant Firebox (Main Furnace Chamber) */}
      <mesh position={[0, 3.4, 0]} castShadow receiveShadow>
        <boxGeometry args={[6.0, 4.6, 5.0]} />
        <meshStandardMaterial
          ref={radiantBoxRef}
          color={isAlarm ? '#7f1d1d' : '#475569'}
          metalness={0.6}
          roughness={0.4}
          emissive={emissiveColor}
          emissiveIntensity={isHighOrCritical ? 0.4 : 0}
        />
      </mesh>

      {/* External Structural Buckstays / Steel Columns */}
      {[-2.8, -0.9, 0.9, 2.8].map((x, idx) => (
        <React.Fragment key={idx}>
          <mesh position={[x, 3.4, 2.58]}>
            <boxGeometry args={[0.2, 4.8, 0.2]} />
            <meshStandardMaterial color="#0f172a" metalness={0.8} roughness={0.3} />
          </mesh>
          <mesh position={[x, 3.4, -2.58]}>
            <boxGeometry args={[0.2, 4.8, 0.2]} />
            <meshStandardMaterial color="#0f172a" metalness={0.8} roughness={0.3} />
          </mesh>
        </React.Fragment>
      ))}

      {/* Convection Section Transition Hood */}
      <mesh position={[0, 6.2, 0]} castShadow>
        <cylinderGeometry args={[2.0, 2.8, 1.2, 8]} />
        <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Convection Tube Bank Box */}
      <mesh position={[0, 7.4, 0]} castShadow>
        <boxGeometry args={[3.6, 1.4, 3.2]} />
        <meshStandardMaterial color="#475569" metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Tall Flue Gas Stack */}
      <mesh ref={stackRef as any} position={[0, 12.0, 0]} castShadow>
        <cylinderGeometry args={[0.8, 1.1, 8.0, 18]} />
        <meshStandardMaterial
          ref={stackRef}
          color="#64748b"
          metalness={0.7}
          roughness={0.3}
          emissive={emissiveColor}
          emissiveIntensity={isHighOrCritical ? 0.2 : 0}
        />
      </mesh>

      {/* Stack Aircraft Warning Bands (Red / White rings) */}
      <mesh position={[0, 14.8, 0]}>
        <cylinderGeometry args={[0.83, 0.86, 0.8, 18]} />
        <meshStandardMaterial color="#dc2626" metalness={0.3} roughness={0.5} />
      </mesh>
      <mesh position={[0, 15.6, 0]}>
        <cylinderGeometry args={[0.81, 0.83, 0.8, 18]} />
        <meshStandardMaterial color="#f8fafc" metalness={0.3} roughness={0.5} />
      </mesh>

      {/* Access Platforms / Walkways */}
      <mesh position={[0, 5.7, 0]}>
        <boxGeometry args={[6.6, 0.12, 5.6]} />
        <meshStandardMaterial color="#1e293b" metalness={0.7} roughness={0.4} />
      </mesh>
    </group>
  )
}
