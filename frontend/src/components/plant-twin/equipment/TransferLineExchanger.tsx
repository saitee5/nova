import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface TransferLineExchangerProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const TransferLineExchanger: React.FC<TransferLineExchangerProps> = ({
  equipment,
  isSelected,
  onClick,
}) => {
  const shellMatRef = useRef<THREE.MeshStandardMaterial>(null)
  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (shellMatRef.current && isHighOrCritical) {
      const pulse = (Math.sin(state.clock.elapsedTime * 4) + 1) * 0.5
      shellMatRef.current.emissiveIntensity = 0.25 + pulse * 0.5
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
      {/* Concrete Foundation Saddles */}
      <mesh position={[-2.4, 0.4, 0]} receiveShadow>
        <boxGeometry args={[0.8, 0.8, 2.2]} />
        <meshStandardMaterial color="#334155" roughness={0.9} />
      </mesh>
      <mesh position={[2.4, 0.4, 0]} receiveShadow>
        <boxGeometry args={[0.8, 0.8, 2.2]} />
        <meshStandardMaterial color="#334155" roughness={0.9} />
      </mesh>

      {/* Main Horizontal Shell Body (Rotated Cylinder) */}
      <mesh
        position={[0, 1.8, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
        receiveShadow
      >
        <cylinderGeometry args={[1.1, 1.1, 7.2, 24]} />
        <meshStandardMaterial
          ref={shellMatRef}
          color={isHighOrCritical ? '#991b1b' : '#475569'}
          metalness={0.7}
          roughness={0.3}
          emissive={emissiveColor}
          emissiveIntensity={isHighOrCritical ? 0.3 : 0}
        />
      </mesh>

      {/* Flanged Hemispherical Channel Heads on Both Ends */}
      <mesh position={[-3.6, 1.8, 0]} rotation={[0, 0, -Math.PI / 2]}>
        <sphereGeometry args={[1.1, 16, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.2} />
      </mesh>
      <mesh position={[3.6, 1.8, 0]} rotation={[0, 0, Math.PI / 2]}>
        <sphereGeometry args={[1.1, 16, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Stiffening Shell Rings */}
      {[-2.0, -0.7, 0.7, 2.0].map((x, i) => (
        <mesh key={i} position={[x, 1.8, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[1.14, 1.14, 0.15, 24]} />
          <meshStandardMaterial color="#1e293b" metalness={0.9} roughness={0.2} />
        </mesh>
      ))}

      {/* Top Steam Drum / Risers Takeoff Nozzles */}
      <mesh position={[-1.2, 3.1, 0]} castShadow>
        <cylinderGeometry args={[0.3, 0.3, 1.2, 16]} />
        <meshStandardMaterial color="#64748b" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[1.2, 3.1, 0]} castShadow>
        <cylinderGeometry args={[0.3, 0.3, 1.2, 16]} />
        <meshStandardMaterial color="#64748b" metalness={0.7} roughness={0.3} />
      </mesh>
      {/* Top Steam Header Tube connecting nozzles */}
      <mesh position={[0, 3.7, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.38, 0.38, 3.6, 16]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Selected Indicator Ring on Floor */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[4.2, 4.6, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}
