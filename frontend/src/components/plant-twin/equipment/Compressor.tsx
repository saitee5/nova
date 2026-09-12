import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface CompressorProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Compressor: React.FC<CompressorProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const casingMatRef = useRef<THREE.MeshStandardMaterial>(null)

  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (casingMatRef.current && isHighOrCritical) {
      const speed = riskTier === 'CRITICAL' ? 9 : 4
      const pulse = (Math.sin(state.clock.elapsedTime * speed) + 1) * 0.5
      casingMatRef.current.emissiveIntensity = 0.3 + pulse * (riskTier === 'CRITICAL' ? 1.1 : 0.5)
    }
  })

  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000
  const baseColor = isAlarm ? '#991b1b' : '#334155'

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
      {/* Heavy Structural Steel Skid Baseplate */}
      <mesh position={[0, 0.25, 0]} receiveShadow>
        <boxGeometry args={[6.8, 0.5, 3.8]} />
        <meshStandardMaterial color="#1e293b" metalness={0.6} roughness={0.7} />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.55, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[3.8, 4.3, 24]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Driver Unit: Steam Turbine / Electric Motor (Left Section) */}
      <group position={[-1.8, 1.3, 0]}>
        {/* Motor / Turbine Body */}
        <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.9, 0.9, 2.4, 16]} />
          <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
        </mesh>
        {/* Cooling Fins / Ribs */}
        <mesh rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.95, 0.95, 1.8, 16]} />
          <meshStandardMaterial color="#334155" metalness={0.6} roughness={0.5} wireframe />
        </mesh>
        {/* Terminal Junction Box */}
        <mesh position={[0, 0.95, 0.3]}>
          <boxGeometry args={[0.7, 0.5, 0.5]} />
          <meshStandardMaterial color="#64748b" metalness={0.7} roughness={0.3} />
        </mesh>
      </group>

      {/* Flexible Shaft Coupling Guard (Center) */}
      <mesh position={[-0.4, 1.3, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.45, 0.45, 0.7, 12]} />
        <meshStandardMaterial color="#eab308" metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Centrifugal Compressor Casing (Right Section) */}
      <group position={[1.4, 1.4, 0]}>
        {/* Barrel / Split Casing */}
        <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
          <cylinderGeometry args={[1.1, 1.1, 2.6, 18]} />
          <meshStandardMaterial
            ref={casingMatRef}
            color={baseColor}
            metalness={0.7}
            roughness={0.3}
            emissive={emissiveColor}
            emissiveIntensity={isHighOrCritical ? 0.4 : 0}
          />
        </mesh>
        {/* Discharge Scroll Volute */}
        <mesh position={[0.5, 0.2, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[1.15, 0.25, 8, 16]} />
          <meshStandardMaterial color="#475569" metalness={0.8} roughness={0.2} />
        </mesh>
        {/* Suction Nozzle (Top) */}
        <mesh position={[-0.4, 1.4, 0]}>
          <cylinderGeometry args={[0.3, 0.3, 0.8, 12]} />
          <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.2} />
        </mesh>
        {/* Discharge Nozzle (Side / Top) */}
        <mesh position={[0.6, 1.4, 0]}>
          <cylinderGeometry args={[0.25, 0.25, 0.8, 12]} />
          <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.2} />
        </mesh>
      </group>

      {/* Lube Oil Console / Filter Skid */}
      <group position={[1.2, 0.8, -1.2]}>
        <mesh>
          <boxGeometry args={[1.4, 0.9, 0.8]} />
          <meshStandardMaterial color="#475569" metalness={0.5} roughness={0.5} />
        </mesh>
        {/* Dual Oil Filter Cannisters */}
        {[-0.3, 0.3].map((x, idx) => (
          <mesh key={idx} position={[x, 0.6, 0]}>
            <cylinderGeometry args={[0.16, 0.16, 0.6, 10]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
          </mesh>
        ))}
      </group>
    </group>
  )
}
