import React from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState } from '../utils/riskUtils'

interface BurnerProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Burner: React.FC<BurnerProps> = ({ equipment, isSelected, onClick }) => {
  const riskTier = getRiskState(equipment)
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL' || equipment.anomalyDetected

  // Burner flame color based on status / fault
  const flameColor = isAlarm ? '#ef4444' : '#38bdf8'

  return (
    <group
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
      {/* Burner Register Flange Base */}
      <mesh position={[0, 0.1, 0]} castShadow>
        <cylinderGeometry args={[0.45, 0.5, 0.2, 16]} />
        <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.3} />
      </mesh>

      {/* Burner Gun Barrel */}
      <mesh position={[0, 0.35, 0]} castShadow>
        <cylinderGeometry args={[0.18, 0.22, 0.35, 12]} />
        <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.4} />
      </mesh>

      {/* Flame Tip Cone (Internal / Optical Monitor representation) */}
      <mesh position={[0, 0.65, 0]}>
        <coneGeometry args={[0.24, 0.5, 12]} />
        <meshBasicMaterial color={flameColor} transparent opacity={0.85} />
      </mesh>

      {/* Flame Glow Light */}
      <pointLight
        position={[0, 0.7, 0]}
        color={flameColor}
        intensity={isAlarm ? 1.5 : 0.8}
        distance={3.5}
      />

      {/* Selection Ring */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.7, 0.9, 24]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}
