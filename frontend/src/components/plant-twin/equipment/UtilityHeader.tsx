import React from 'react'
import { EquipmentItem } from '../types'

interface UtilityHeaderProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const UtilityHeader: React.FC<UtilityHeaderProps> = ({ equipment, isSelected, onClick }) => {

  // Color code based on equipment tag/service
  const isFuelGas = equipment.tag.includes('501')
  const isSteam = equipment.tag.includes('502')
  const headerColor = isFuelGas ? '#eab308' : isSteam ? '#94a3b8' : '#38bdf8'

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
      {/* Pipe Rack Structural Bents / H-Beam Stanchions */}
      {[-3.0, 0, 3.0].map((x, idx) => (
        <group key={idx} position={[x, 0, 0]}>
          {/* Vertical Columns */}
          <mesh position={[0, 0.9, -0.6]} castShadow>
            <boxGeometry args={[0.2, 1.8, 0.2]} />
            <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.4} />
          </mesh>
          <mesh position={[0, 0.9, 0.6]} castShadow>
            <boxGeometry args={[0.2, 1.8, 0.2]} />
            <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.4} />
          </mesh>
          {/* Cross Beam */}
          <mesh position={[0, 1.8, 0]} castShadow>
            <boxGeometry args={[0.2, 0.15, 1.6]} />
            <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.3} />
          </mesh>
        </group>
      ))}

      {/* Main Longitudinal Header Pipe */}
      <mesh position={[0, 2.1, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.35, 0.35, 7.5, 18]} />
        <meshStandardMaterial color={headerColor} metalness={0.6} roughness={0.3} />
      </mesh>

      {/* Flanged Takeoff Branches (Vertical T-connections) */}
      {[-2.0, -0.8, 0.8, 2.0].map((x, idx) => (
        <group key={idx} position={[x, 2.1, 0]}>
          <mesh position={[0, 0.5, 0]} castShadow>
            <cylinderGeometry args={[0.18, 0.18, 1.0, 14]} />
            <meshStandardMaterial color={headerColor} metalness={0.6} roughness={0.3} />
          </mesh>
          {/* Branch Top Flange */}
          <mesh position={[0, 1.0, 0]}>
            <cylinderGeometry args={[0.28, 0.28, 0.08, 14]} />
            <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
          </mesh>
        </group>
      ))}

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[8.2, 2.0]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.3} />
        </mesh>
      )}
    </group>
  )
}
