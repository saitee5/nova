import React from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'

interface ESDValveProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const ESDValve: React.FC<ESDValveProps> = ({ equipment, isSelected, onClick }) => {

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
      {/* Pipe Flange Spool Body */}
      <mesh position={[0, 0.4, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.3, 0.3, 1.6, 16]} />
        <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.3} />
      </mesh>

      {/* Flange Rings */}
      {[-0.7, 0.7].map((x, idx) => (
        <mesh key={idx} position={[x, 0.4, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.48, 0.48, 0.12, 16]} />
          <meshStandardMaterial color="#1e293b" metalness={0.9} roughness={0.2} />
        </mesh>
      ))}

      {/* Valve Yoke Neck */}
      <mesh position={[0, 0.9, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.22, 0.8, 12]} />
        <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Prominent Red Safety Actuator Housing (SIL-3 Pneumatic Spring-Return) */}
      <mesh position={[0, 1.8, 0]} castShadow>
        <cylinderGeometry args={[0.55, 0.55, 1.0, 18]} />
        <meshStandardMaterial color="#dc2626" metalness={0.4} roughness={0.3} />
      </mesh>

      {/* Actuator Top Dome / Yellow Position Indicator */}
      <mesh position={[0, 2.4, 0]}>
        <cylinderGeometry args={[0.2, 0.2, 0.25, 14]} />
        <meshStandardMaterial color="#facc15" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Manual Override Handwheel */}
      <mesh position={[0.6, 1.8, 0]} rotation={[0, 0, Math.PI / 2]}>
        <torusGeometry args={[0.32, 0.04, 8, 18]} />
        <meshStandardMaterial color="#f8fafc" metalness={0.6} roughness={0.3} />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.2, 1.5, 24]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}
