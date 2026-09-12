import React from 'react'
import * as THREE from 'three'

interface PipeProps {
  start: [number, number, number]
  end: [number, number, number]
  radius?: number
  color?: string
}

export const Pipe: React.FC<PipeProps> = ({
  start,
  end,
  radius = 0.25,
  color = '#475569',
}) => {
  const p1 = new THREE.Vector3(...start)
  const p2 = new THREE.Vector3(...end)
  const length = p1.distanceTo(p2)
  const midPoint = p1.clone().add(p2).multiplyScalar(0.5)

  return (
    <group position={midPoint.toArray()}>
      <mesh>
        <cylinderGeometry args={[radius, radius, length, 12]} />
        <meshStandardMaterial color={color} metalness={0.7} roughness={0.3} />
      </mesh>
      {/* Pipe Joint Flange */}
      <mesh>
        <cylinderGeometry args={[radius * 1.35, radius * 1.35, radius * 0.4, 12]} />
        <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.2} />
      </mesh>
    </group>
  )
}
