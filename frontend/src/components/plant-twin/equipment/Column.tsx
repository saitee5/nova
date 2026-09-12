import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface ColumnProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Column: React.FC<ColumnProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const shellMatRef = useRef<THREE.MeshStandardMaterial>(null)

  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL'

  // Height varies by column type: C2 Splitter (C-403) is tallest (16m), quench tower (C-302) is wider/medium (12m), pre-flash (C-201) is 10m
  const isTallSplitter = equipment.tag === 'C-403' || equipment.tag === 'C-401'
  const towerHeight = isTallSplitter ? 15.0 : 11.0
  const towerRadius = equipment.tag === 'C-302' ? 1.8 : 1.3

  useFrame((state) => {
    if (shellMatRef.current && isHighOrCritical) {
      const speed = riskTier === 'CRITICAL' ? 8 : 4
      const pulse = (Math.sin(state.clock.elapsedTime * speed) + 1) * 0.5
      shellMatRef.current.emissiveIntensity = 0.25 + pulse * (riskTier === 'CRITICAL' ? 1.0 : 0.5)
    }
  })

  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000
  const baseColor = isAlarm ? '#991b1b' : '#475569'

  // Intermediate platform levels
  const platformCount = isTallSplitter ? 4 : 3
  const platformInterval = towerHeight / (platformCount + 1)

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
      {/* Foundation Base Skirt */}
      <mesh position={[0, 0.4, 0]} receiveShadow>
        <cylinderGeometry args={[towerRadius * 1.3, towerRadius * 1.45, 0.8, 16]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.85, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[towerRadius * 1.8, towerRadius * 2.2, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Main Tower Shell */}
      <mesh position={[0, towerHeight / 2 + 0.8, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[towerRadius, towerRadius, towerHeight, 24]} />
        <meshStandardMaterial
          ref={shellMatRef}
          color={baseColor}
          metalness={0.65}
          roughness={0.35}
          emissive={emissiveColor}
          emissiveIntensity={isHighOrCritical ? 0.35 : 0}
        />
      </mesh>

      {/* Top Hemispherical Head */}
      <mesh position={[0, towerHeight + 0.8, 0]} castShadow>
        <sphereGeometry args={[towerRadius, 18, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#64748b" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Top Overhead Vapour Nozzle */}
      <mesh position={[0, towerHeight + towerRadius + 0.8, 0]}>
        <cylinderGeometry args={[0.3, 0.3, 0.9, 12]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Circular Platform Rings & Railings */}
      {Array.from({ length: platformCount }).map((_, i) => {
        const yPos = (i + 1) * platformInterval + 0.8
        return (
          <group key={i} position={[0, yPos, 0]}>
            {/* Grating Platform */}
            <mesh>
              <cylinderGeometry args={[towerRadius * 1.65, towerRadius * 1.65, 0.1, 16]} />
              <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.4} />
            </mesh>
            {/* Outer Safety Handrail */}
            <mesh position={[0, 0.45, 0]}>
              <torusGeometry args={[towerRadius * 1.62, 0.04, 4, 16]} />
              <meshStandardMaterial color="#94a3b8" metalness={0.9} roughness={0.2} />
            </mesh>
          </group>
        )
      })}

      {/* Vertical Caged Ladder */}
      <group position={[towerRadius + 0.25, towerHeight / 2 + 0.8, 0]}>
        <mesh>
          <boxGeometry args={[0.15, towerHeight, 0.4]} />
          <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
        </mesh>
      </group>

      {/* Base Tag Plaque */}
      <mesh position={[0, 0.9, towerRadius * 1.35]}>
        <boxGeometry args={[1.4, 0.35, 0.08]} />
        <meshBasicMaterial color="#0f172a" />
      </mesh>
    </group>
  )
}
