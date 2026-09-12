import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface PumpProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Pump: React.FC<PumpProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const voluteMatRef = useRef<THREE.MeshStandardMaterial>(null)

  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (voluteMatRef.current && isHighOrCritical) {
      const speed = riskTier === 'CRITICAL' ? 8 : 4
      const pulse = (Math.sin(state.clock.elapsedTime * speed) + 1) * 0.5
      voluteMatRef.current.emissiveIntensity = 0.3 + pulse * (riskTier === 'CRITICAL' ? 1.0 : 0.5)
    }
  })

  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000
  const baseColor = isAlarm ? '#991b1b' : equipment.status === 'idle' ? '#64748b' : '#334155'

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
      {/* Concrete Plinth & Baseplate */}
      <mesh position={[0, 0.15, 0]} receiveShadow>
        <boxGeometry args={[3.4, 0.3, 1.8]} />
        <meshStandardMaterial color="#1e293b" metalness={0.5} roughness={0.8} />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.35, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[2.0, 2.3, 20]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Electric Induction Motor (Left) */}
      <group position={[-0.85, 0.75, 0]}>
        {/* Motor Stator Body */}
        <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.45, 0.45, 1.3, 16]} />
          <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
        </mesh>
        {/* Terminal Box */}
        <mesh position={[0, 0.5, 0.2]}>
          <boxGeometry args={[0.35, 0.25, 0.3]} />
          <meshStandardMaterial color="#64748b" metalness={0.6} roughness={0.4} />
        </mesh>
      </group>

      {/* Shaft Coupling Guard (Center) */}
      <mesh position={[-0.05, 0.75, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.26, 0.26, 0.4, 12]} />
        <meshStandardMaterial color="#f97316" metalness={0.5} roughness={0.4} />
      </mesh>

      {/* Pump Bearing Frame & Volute Casing (Right) */}
      <group position={[0.75, 0.75, 0]}>
        {/* Bearing Housing */}
        <mesh position={[-0.35, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.28, 0.28, 0.4, 12]} />
          <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.3} />
        </mesh>

        {/* Spiral Volute Casing */}
        <mesh castShadow receiveShadow>
          <torusGeometry args={[0.42, 0.24, 10, 16]} />
          <meshStandardMaterial
            ref={voluteMatRef}
            color={baseColor}
            metalness={0.75}
            roughness={0.25}
            emissive={emissiveColor}
            emissiveIntensity={isHighOrCritical ? 0.4 : 0}
          />
        </mesh>

        {/* Axial End Suction Flange (Pointing +X) */}
        <group position={[0.5, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <mesh>
            <cylinderGeometry args={[0.18, 0.18, 0.35, 12]} />
            <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.2} />
          </mesh>
          <mesh position={[0, 0.18, 0]}>
            <cylinderGeometry args={[0.3, 0.3, 0.08, 12]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.9} roughness={0.2} />
          </mesh>
        </group>

        {/* Top Radial Discharge Nozzle (Pointing +Y) */}
        <group position={[0, 0.5, 0]}>
          <mesh>
            <cylinderGeometry args={[0.15, 0.15, 0.35, 12]} />
            <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.2} />
          </mesh>
          <mesh position={[0, 0.18, 0]}>
            <cylinderGeometry args={[0.26, 0.26, 0.08, 12]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.9} roughness={0.2} />
          </mesh>
        </group>
      </group>
    </group>
  )
}
