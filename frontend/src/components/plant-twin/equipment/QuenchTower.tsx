import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface QuenchTowerProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const QuenchTower: React.FC<QuenchTowerProps> = ({ equipment, isSelected, onClick }) => {
  const columnMatRef = useRef<THREE.MeshStandardMaterial>(null)
  const liquidBandRef = useRef<THREE.MeshStandardMaterial>(null)

  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (columnMatRef.current && isHighOrCritical) {
      const pulse = (Math.sin(state.clock.elapsedTime * 4) + 1) * 0.5
      columnMatRef.current.emissiveIntensity = 0.25 + pulse * 0.5
    }
    if (liquidBandRef.current) {
      // Subtle shimmer in the liquid level band
      liquidBandRef.current.opacity = 0.75 + Math.sin(state.clock.elapsedTime * 2) * 0.15
    }
  })

  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000

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
      {/* Foundation Octagon Base */}
      <mesh position={[0, 0.4, 0]} receiveShadow>
        <cylinderGeometry args={[2.8, 3.2, 0.8, 8]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Skirt Support */}
      <mesh position={[0, 1.8, 0]} castShadow>
        <cylinderGeometry args={[2.2, 2.4, 2.0, 24]} />
        <meshStandardMaterial color="#334155" metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Visible Liquid Level Band at Lower Section */}
      <mesh position={[0, 3.4, 0]}>
        <cylinderGeometry args={[2.23, 2.23, 1.2, 24]} />
        <meshStandardMaterial
          ref={liquidBandRef}
          color="#06b6d4" // Cyan / Aqua liquid holdup indicator
          transparent
          opacity={0.8}
          metalness={0.8}
          roughness={0.1}
        />
      </mesh>

      {/* Main Quench Column Shell (Height: 18m) */}
      <mesh position={[0, 10.5, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[2.2, 2.2, 17.0, 28]} />
        <meshStandardMaterial
          ref={columnMatRef}
          color={isHighOrCritical ? '#991b1b' : '#64748b'}
          metalness={0.6}
          roughness={0.3}
          emissive={emissiveColor}
          emissiveIntensity={isHighOrCritical ? 0.3 : 0}
        />
      </mesh>

      {/* Top Hemispherical Head */}
      <mesh position={[0, 19.0, 0]}>
        <sphereGeometry args={[2.2, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Top Overhead Vapour Takeoff Nozzle */}
      <mesh position={[0, 20.4, 0]} castShadow>
        <cylinderGeometry args={[0.55, 0.55, 1.6, 16]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Maintenance Platforms / Circular Walkways */}
      {[5.5, 9.5, 13.5, 17.5].map((y, idx) => (
        <group key={idx} position={[0, y, 0]}>
          {/* Platform Floor */}
          <mesh rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[2.22, 3.3, 24]} />
            <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.3} side={THREE.DoubleSide} />
          </mesh>
          {/* Platform Outer Handrail */}
          <mesh position={[0, 0.45, 0]}>
            <cylinderGeometry args={[3.25, 3.25, 0.9, 24, 1, true]} />
            <meshStandardMaterial color="#94a3b8" wireframe transparent opacity={0.6} />
          </mesh>
        </group>
      ))}

      {/* Vertical Caged Ladder Structure on Column Side */}
      <mesh position={[2.7, 10.5, 0]}>
        <boxGeometry args={[0.3, 17.0, 0.6]} />
        <meshStandardMaterial color="#0f172a" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Selected Indicator Ring */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[3.8, 4.3, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}
