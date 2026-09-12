import React, { useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'

interface SensorMarkerProps {
  position: [number, number, number]
  type?: 'TT' | 'PT' | 'FT' | 'GT' | 'VT'
  status?: 'normal' | 'warning' | 'critical'
}

export const SensorMarker: React.FC<SensorMarkerProps> = ({
  position,
  status = 'normal',
}) => {
  const ledRef = useRef<THREE.MeshBasicMaterial>(null)

  const ledColor =
    status === 'critical' ? '#ef4444' : status === 'warning' ? '#f59e0b' : '#22c55e'

  useFrame((state) => {
    if (ledRef.current) {
      const blink = Math.sin(state.clock.elapsedTime * (status === 'critical' ? 10 : 3)) > 0
      ledRef.current.opacity = blink ? 1.0 : 0.3
    }
  })

  return (
    <group position={position}>
      {/* Sensor Stand / Impulse Line */}
      <mesh position={[0, 0.4, 0]}>
        <cylinderGeometry args={[0.04, 0.04, 0.8, 8]} />
        <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
      </mesh>

      {/* Explosion-proof Transmitter Housing (Puck/Canister) */}
      <mesh position={[0, 0.95, 0]}>
        <cylinderGeometry args={[0.22, 0.22, 0.35, 12]} />
        <meshStandardMaterial color="#0284c7" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Front Glass Display Window */}
      <mesh position={[0, 0.95, 0.12]}>
        <cylinderGeometry args={[0.16, 0.16, 0.04, 12]} />
        <meshStandardMaterial color="#0f172a" metalness={0.9} roughness={0.1} />
      </mesh>

      {/* Blinking Health Status LED */}
      <mesh position={[0.1, 1.05, 0.14]}>
        <sphereGeometry args={[0.035, 8, 8]} />
        <meshBasicMaterial ref={ledRef} color={ledColor} transparent />
      </mesh>
    </group>
  )
}
