import React from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState } from '../utils/riskUtils'

interface GasDetectorProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const GasDetector: React.FC<GasDetectorProps> = ({ equipment, isSelected, onClick }) => {
  const riskTier = getRiskState(equipment)
  const isElevated = (equipment.telemetry.gasConcentration ?? 0) > 0.1 || riskTier !== 'LOW'

  const statusColor = isElevated ? '#ef4444' : '#22c55e'

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
      {/* Ground Mount Base Plate */}
      <mesh position={[0, 0.05, 0]} receiveShadow>
        <cylinderGeometry args={[0.35, 0.4, 0.1, 12]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Structural Stanchion Post */}
      <mesh position={[0, 0.8, 0]} castShadow>
        <cylinderGeometry args={[0.08, 0.08, 1.5, 12]} />
        <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
      </mesh>

      {/* Explosion-Proof Transmitter Junction Box */}
      <mesh position={[0, 1.45, 0]} castShadow>
        <boxGeometry args={[0.4, 0.5, 0.35]} />
        <meshStandardMaterial color="#0284c7" metalness={0.5} roughness={0.4} />
      </mesh>

      {/* Optical IR Gas Sensor Diffusion Sinter Head (Facing Downward) */}
      <mesh position={[0, 1.05, 0]}>
        <cylinderGeometry args={[0.12, 0.12, 0.3, 16]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Local Status LED / Beacon Lens */}
      <mesh position={[0, 1.85, 0]}>
        <sphereGeometry args={[0.14, 16, 16]} />
        <meshStandardMaterial
          color={statusColor}
          emissive={statusColor}
          emissiveIntensity={0.8}
        />
      </mesh>

      {/* Light glow from beacon */}
      <pointLight position={[0, 1.9, 0]} color={statusColor} intensity={0.6} distance={2.5} />

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.6, 0.8, 20]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}
