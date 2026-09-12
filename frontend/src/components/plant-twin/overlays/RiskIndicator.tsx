import React, { useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'

interface RiskIndicatorProps {
  equipment: EquipmentItem
}

export const RiskIndicator: React.FC<RiskIndicatorProps> = ({ equipment }) => {
  const groupRef = useRef<THREE.Group>(null)
  const riskTier = getRiskState(equipment)

  // LOW has NO indicator badge
  if (riskTier === 'LOW') {
    return null
  }

  // Height offset based on equipment type
  let heightOffset = 6.5
  if (equipment.type === 'column') heightOffset = 17.5
  else if (equipment.type === 'furnace') heightOffset = 17.0
  else if (equipment.type === 'tank') heightOffset = 8.5
  else if (equipment.type === 'compressor') heightOffset = 4.8
  else if (equipment.type === 'pump' || equipment.type === 'valve') heightOffset = 3.5

  const isCritical = riskTier === 'CRITICAL'
  const badgeColor = RISK_COLORS[riskTier].hex

  useFrame((state) => {
    if (groupRef.current) {
      // Billboard towards camera
      groupRef.current.quaternion.copy(state.camera.quaternion)

      // Subtle float bobbing
      const bob = Math.sin(state.clock.elapsedTime * 2.5 + equipment.position[0]) * 0.15
      groupRef.current.position.y = equipment.position[1] + heightOffset + bob
    }
  })

  return (
    <group
      ref={groupRef}
      position={[equipment.position[0], equipment.position[1] + heightOffset, equipment.position[2]]}
    >
      {/* Anchor line dropping down to equipment */}
      <mesh position={[0, -heightOffset * 0.4, 0]}>
        <cylinderGeometry args={[0.03, 0.03, heightOffset * 0.8, 6]} />
        <meshBasicMaterial color={badgeColor} transparent opacity={0.5} />
      </mesh>

      {/* Outer Hexagon / Shield Frame */}
      <mesh rotation={[0, 0, Math.PI / 4]}>
        <boxGeometry args={[1.5, 1.5, 0.12]} />
        <meshBasicMaterial color="#0f172a" />
      </mesh>

      {/* Inner Colored Warning Diamond */}
      <mesh rotation={[0, 0, Math.PI / 4]} position={[0, 0, 0.08]}>
        <boxGeometry args={[1.2, 1.2, 0.1]} />
        <meshBasicMaterial color={badgeColor} />
      </mesh>

      {/* Exclamation Symbol Bars */}
      <group position={[0, 0, 0.16]}>
        {/* Main Exclamation Stem */}
        <mesh position={[0, 0.12, 0]}>
          <boxGeometry args={[0.18, 0.5, 0.05]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
        {/* Exclamation Dot */}
        <mesh position={[0, -0.3, 0]}>
          <boxGeometry args={[0.18, 0.18, 0.05]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      </group>

      {/* Critical outer glow pulse ring */}
      {isCritical && (
        <mesh position={[0, 0, -0.05]}>
          <ringGeometry args={[1.1, 1.35, 16]} />
          <meshBasicMaterial color="#ef4444" transparent opacity={0.8} />
        </mesh>
      )}
    </group>
  )
}
