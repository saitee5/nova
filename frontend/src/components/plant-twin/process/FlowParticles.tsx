import React, { useRef, useMemo } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'

interface FlowParticlesProps {
  curve: THREE.CatmullRomCurve3
  flowRate?: number
  color?: string
  particleCount?: number
  radius?: number
}

export const FlowParticles: React.FC<FlowParticlesProps> = ({
  curve,
  flowRate = 200,
  color = '#38bdf8',
  particleCount = 12,
  radius = 0.15,
}) => {
  const instancedRef = useRef<THREE.InstancedMesh>(null)
  const dummy = useMemo(() => new THREE.Object3D(), [])

  // Spread initial offsets uniformly along the curve [0, 1)
  const initialOffsets = useMemo(() => {
    return Array.from({ length: particleCount }, (_, i) => i / particleCount)
  }, [particleCount])

  // Speed derived from flow rate
  // Normal flow rate ranges 100-500 m3/h
  const speed = useMemo(() => {
    return Math.max(0.04, (flowRate / 300) * 0.12)
  }, [flowRate])

  useFrame((_, delta) => {
    if (!instancedRef.current) return

    for (let i = 0; i < particleCount; i++) {
      initialOffsets[i] = (initialOffsets[i] + speed * delta) % 1.0
      const t = initialOffsets[i]
      const pos = curve.getPointAt(t)
      const tangent = curve.getTangentAt(t).normalize()

      dummy.position.copy(pos)
      // Orient particle along tangent
      dummy.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), tangent)
      dummy.scale.set(radius, radius * 2.2, radius)
      dummy.updateMatrix()

      instancedRef.current.setMatrixAt(i, dummy.matrix)
    }

    instancedRef.current.instanceMatrix.needsUpdate = true
  })

  return (
    <instancedMesh
      ref={instancedRef}
      args={[undefined as any, undefined as any, particleCount]}
    >
      <capsuleGeometry args={[0.5, 1.0, 4, 8]} />
      <meshBasicMaterial color={color} transparent opacity={0.85} />
    </instancedMesh>
  )
}
