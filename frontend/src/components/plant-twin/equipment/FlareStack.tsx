import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { useFrame } from '@react-three/fiber'

interface FlareStackProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const FlareStack: React.FC<FlareStackProps> = ({ equipment, isSelected, onClick }) => {
  const flameRef = useRef<THREE.Mesh>(null)
  const lightRef = useRef<THREE.PointLight>(null)

  useFrame((state) => {
    if (flameRef.current) {
      // Realistic flame flicker
      const t = state.clock.elapsedTime * 6
      const s = 1.0 + Math.sin(t) * 0.15 + Math.cos(t * 1.7) * 0.1
      flameRef.current.scale.set(s, s * (1 + Math.sin(t * 2) * 0.1), s)
    }
    if (lightRef.current) {
      lightRef.current.intensity = 2.0 + Math.sin(state.clock.elapsedTime * 8) * 0.8
    }
  })

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
      {/* Heavy Octagonal Reinforced Base */}
      <mesh position={[0, 0.4, 0]} receiveShadow>
        <cylinderGeometry args={[2.5, 3.2, 0.8, 8]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Flare Riser Stack Cylinder (Height: 26m) */}
      <mesh position={[0, 13.5, 0]} castShadow>
        <cylinderGeometry args={[0.55, 0.9, 25.0, 18]} />
        <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
      </mesh>

      {/* Structural Support Derrick (Four Corner Legs) */}
      {[-1.4, 1.4].map((x) =>
        [-1.4, 1.4].map((z) => (
          <mesh key={`${x}-${z}`} position={[x, 7.5, z]} castShadow>
            <cylinderGeometry args={[0.1, 0.18, 14.0, 8]} />
            <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.4} />
          </mesh>
        ))
      )}

      {/* Derrick Cross-bracing Rings */}
      {[4.0, 8.0, 12.0].map((y, idx) => (
        <mesh key={idx} position={[0, y, 0]}>
          <boxGeometry args={[3.0, 0.15, 3.0]} />
          <meshStandardMaterial color="#1e293b" wireframe transparent opacity={0.7} />
        </mesh>
      ))}

      {/* Smokeless Steam Injection Ring at Flare Tip */}
      <mesh position={[0, 26.2, 0]}>
        <torusGeometry args={[0.7, 0.12, 12, 24]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Flare Flame Cone */}
      <mesh ref={flameRef} position={[0, 27.6, 0]}>
        <coneGeometry args={[0.85, 2.5, 14]} />
        <meshBasicMaterial color="#f97316" transparent opacity={0.9} />
      </mesh>

      {/* Inner Hot Core Flame */}
      <mesh position={[0, 27.2, 0]}>
        <coneGeometry args={[0.45, 1.4, 12]} />
        <meshBasicMaterial color="#fef08a" />
      </mesh>

      {/* Dynamic Night/Dusk Light Source */}
      <pointLight
        ref={lightRef}
        position={[0, 28.5, 0]}
        color="#ea580c"
        intensity={2.2}
        distance={60}
      />

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[3.6, 4.2, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}
