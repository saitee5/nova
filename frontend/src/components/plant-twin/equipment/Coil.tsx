import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface CoilProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Coil: React.FC<CoilProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const coilMatRef = useRef<THREE.MeshStandardMaterial>(null)

  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (coilMatRef.current && isHighOrCritical) {
      const speed = riskTier === 'CRITICAL' ? 8 : 4
      const pulse = (Math.sin(state.clock.elapsedTime * speed) + 1) * 0.5
      coilMatRef.current.emissiveIntensity = 0.5 + pulse * (riskTier === 'CRITICAL' ? 1.2 : 0.6)
    }
  })

  // Radiant coil color is glowing cherry-red/orange or amber under normal pyrolysis
  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0xd97706

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
      {/* Structural Support Frame */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[4.2, 4.8, 0.6]} />
        <meshBasicMaterial wireframe color="#334155" />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, -2.5, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[2.5, 2.9, 24]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Vertical Serpentine Passes */}
      {[-1.5, -0.9, -0.3, 0.3, 0.9, 1.5].map((x, idx) => (
        <group key={idx} position={[x, 0, 0]}>
          {/* Vertical tube */}
          <mesh castShadow>
            <cylinderGeometry args={[0.12, 0.12, 3.8, 12]} />
            <meshStandardMaterial
              ref={idx === 0 ? coilMatRef : undefined}
              color="#b45309"
              metalness={0.7}
              roughness={0.3}
              emissive={emissiveColor}
              emissiveIntensity={isHighOrCritical ? 0.8 : 0.3}
            />
          </mesh>

          {/* Top Return U-Bend */}
          {idx % 2 === 0 && (
            <mesh position={[0.3, 1.9, 0]} rotation={[0, 0, Math.PI]}>
              <torusGeometry args={[0.3, 0.12, 8, 12, Math.PI]} />
              <meshStandardMaterial
                color="#b45309"
                metalness={0.7}
                roughness={0.3}
                emissive={emissiveColor}
                emissiveIntensity={isHighOrCritical ? 0.8 : 0.3}
              />
            </mesh>
          )}

          {/* Bottom Return U-Bend */}
          {idx % 2 === 1 && idx < 5 && (
            <mesh position={[0.3, -1.9, 0]}>
              <torusGeometry args={[0.3, 0.12, 8, 12, Math.PI]} />
              <meshStandardMaterial
                color="#b45309"
                metalness={0.7}
                roughness={0.3}
                emissive={emissiveColor}
                emissiveIntensity={isHighOrCritical ? 0.8 : 0.3}
              />
            </mesh>
          )}
        </group>
      ))}

      {/* Inlet & Outlet Manifolds */}
      <mesh position={[-1.5, -2.2, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.22, 0.22, 1.2, 12]} />
        <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
      </mesh>
      <mesh position={[1.5, 2.2, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.22, 0.22, 1.2, 12]} />
        <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
      </mesh>
    </group>
  )
}
