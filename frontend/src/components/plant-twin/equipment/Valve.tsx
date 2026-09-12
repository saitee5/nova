import React, { useRef, useMemo } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface ValveProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Valve: React.FC<ValveProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const bodyMatRef = useRef<THREE.MeshStandardMaterial>(null)

  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (bodyMatRef.current && isHighOrCritical) {
      const speed = riskTier === 'CRITICAL' ? 8 : 4
      const pulse = (Math.sin(state.clock.elapsedTime * speed) + 1) * 0.5
      bodyMatRef.current.emissiveIntensity = 0.3 + pulse * (riskTier === 'CRITICAL' ? 1.0 : 0.5)
    }
  })

  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000
  const baseColor = isAlarm ? '#991b1b' : '#475569'

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
      {/* Foundation plinth */}
      <mesh position={[0, 0.15, 0]} receiveShadow>
        <boxGeometry args={[1.8, 0.3, 1.4]} />
        <meshStandardMaterial color="#1e293b" roughness={0.8} />
      </mesh>

      {/* Selected Ring */}
      {isSelected && (
        <mesh position={[0, 0.35, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.2, 1.45, 16]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Valve Body: Opposing Cones (Globe valve shape) */}
      <group position={[0, 0.9, 0]}>
        <mesh position={[-0.3, 0, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <coneGeometry args={[0.32, 0.5, 12]} />
          <meshStandardMaterial
            ref={bodyMatRef}
            color={baseColor}
            metalness={0.7}
            roughness={0.3}
            emissive={emissiveColor}
            emissiveIntensity={isHighOrCritical ? 0.4 : 0}
          />
        </mesh>
        <mesh position={[0.3, 0, 0]} rotation={[0, 0, -Math.PI / 2]} castShadow>
          <coneGeometry args={[0.32, 0.5, 12]} />
          <meshStandardMaterial color={baseColor} metalness={0.7} roughness={0.3} />
        </mesh>

        {/* Flanges at Ends */}
        {[-0.55, 0.55].map((x, idx) => (
          <mesh key={idx} position={[x, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.38, 0.38, 0.1, 12]} />
            <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.2} />
          </mesh>
        ))}

        {/* Valve Bonnet & Stem */}
        <mesh position={[0, 0.4, 0]}>
          <cylinderGeometry args={[0.1, 0.1, 0.7, 8]} />
          <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
        </mesh>

        {/* Pneumatic Diaphragm Actuator (Dome) */}
        <mesh position={[0, 1.0, 0]} castShadow>
          <sphereGeometry args={[0.42, 12, 10, 0, Math.PI * 2, 0, Math.PI / 2]} />
          <meshStandardMaterial color="#0284c7" metalness={0.6} roughness={0.4} />
        </mesh>
        <mesh position={[0, 0.8, 0]}>
          <cylinderGeometry args={[0.42, 0.42, 0.3, 12]} />
          <meshStandardMaterial color="#0369a1" metalness={0.6} roughness={0.4} />
        </mesh>

        {/* Top Position Indicator Pin */}
        <mesh position={[0, 1.45, 0]}>
          <cylinderGeometry args={[0.04, 0.04, 0.3, 6]} />
          <meshStandardMaterial color="#facc15" />
        </mesh>
      </group>
    </group>
  )
}

/**
 * InstancedValves:
 * High-performance instanced rendering for repeated small valves/tie-ins across the plant
 */
export const InstancedValves: React.FC<{
  positions: [number, number, number][]
}> = ({ positions }) => {
  const count = positions.length
  const meshRef = useRef<THREE.InstancedMesh>(null)

  const dummy = useMemo(() => new THREE.Object3D(), [])

  React.useEffect(() => {
    if (!meshRef.current) return
    positions.forEach((pos, i) => {
      dummy.position.set(pos[0], pos[1], pos[2])
      dummy.scale.set(0.7, 0.7, 0.7)
      dummy.updateMatrix()
      meshRef.current?.setMatrixAt(i, dummy.matrix)
    })
    meshRef.current.instanceMatrix.needsUpdate = true
  }, [positions, dummy])

  return (
    <instancedMesh ref={meshRef} args={[undefined as any, undefined as any, count]} castShadow>
      <cylinderGeometry args={[0.2, 0.2, 0.8, 8]} />
      <meshStandardMaterial color="#64748b" metalness={0.7} roughness={0.3} />
    </instancedMesh>
  )
}
