import React, { useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { EquipmentItem } from '../types'
import { getRiskState } from '../utils/riskUtils'

interface AnomalyPulseProps {
  equipment: EquipmentItem
}

export const AnomalyPulse: React.FC<AnomalyPulseProps> = ({ equipment }) => {
  const ringRef1 = useRef<THREE.Mesh>(null)
  const ringRef2 = useRef<THREE.Mesh>(null)
  const cylinderRef = useRef<THREE.Mesh>(null)

  const riskTier = getRiskState(equipment)

  // LOW and MEDIUM have NO pulsing
  if (riskTier === 'LOW' || riskTier === 'MEDIUM') {
    return null
  }

  const isCritical = riskTier === 'CRITICAL'
  const pulseColor = isCritical ? '#ef4444' : '#f97316'
  const speed = isCritical ? 2.8 : 1.6
  const maxRadius = isCritical ? 8.5 : 5.5

  useFrame((state) => {
    const t = state.clock.elapsedTime * speed

    // Ring 1
    if (ringRef1.current) {
      const progress1 = (t % 1.0)
      const scale1 = 0.5 + progress1 * maxRadius
      ringRef1.current.scale.set(scale1, scale1, 1)
      const mat = ringRef1.current.material as THREE.MeshBasicMaterial
      mat.opacity = (1 - progress1) * (isCritical ? 0.9 : 0.6)
    }

    // Ring 2 (staggered by 0.5 cycle)
    if (ringRef2.current) {
      const progress2 = ((t + 0.5) % 1.0)
      const scale2 = 0.5 + progress2 * maxRadius
      ringRef2.current.scale.set(scale2, scale2, 1)
      const mat = ringRef2.current.material as THREE.MeshBasicMaterial
      mat.opacity = (1 - progress2) * (isCritical ? 0.7 : 0.4)
    }

    // Vertical alert column (critical only)
    if (cylinderRef.current && isCritical) {
      const pulse = (Math.sin(state.clock.elapsedTime * 6) + 1) * 0.5
      const mat = cylinderRef.current.material as THREE.MeshBasicMaterial
      mat.opacity = 0.15 + pulse * 0.25
    }
  })

  return (
    <group position={[equipment.position[0], 0.2, equipment.position[2]]}>
      {/* Ground Concentric Expanding Ring 1 */}
      <mesh ref={ringRef1} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.9, 1.15, 32]} />
        <meshBasicMaterial
          color={pulseColor}
          transparent
          opacity={0.8}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      {/* Ground Concentric Expanding Ring 2 */}
      <mesh ref={ringRef2} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.9, 1.15, 32]} />
        <meshBasicMaterial
          color={pulseColor}
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      {/* Localized Vertical Anomaly Beacon for Critical tier */}
      {isCritical && (
        <mesh ref={cylinderRef} position={[0, 8, 0]}>
          <cylinderGeometry args={[1.5, 3.2, 16, 16, 1, true]} />
          <meshBasicMaterial
            color="#ef4444"
            transparent
            opacity={0.2}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      )}
    </group>
  )
}
