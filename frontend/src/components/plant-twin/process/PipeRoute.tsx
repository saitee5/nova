import React, { useMemo } from 'react'
import * as THREE from 'three'
import { PipeRouteDefinition } from '../types'
import { FLUID_COLORS } from '../utils/riskUtils'
import { FlowParticles } from './FlowParticles'

interface PipeRouteProps {
  route: PipeRouteDefinition
  isSelected?: boolean
}

export const PipeRoute: React.FC<PipeRouteProps> = ({ route, isSelected }) => {
  const { curve, tubularSegments } = useMemo(() => {
    const points = route.waypoints.map((p) => new THREE.Vector3(...p))
    // Create CatmullRom with centripetal curve type to prevent large loops
    const c = new THREE.CatmullRomCurve3(points, false, 'centripetal', 0.2)
    const segments = Math.max(24, points.length * 12)
    return { curve: c, tubularSegments: segments }
  }, [route.waypoints])

  const fluidInfo = FLUID_COLORS[route.fluidType] || { hex: '#64748b', threeHex: 0x64748b }
  const pipeRadius = route.nominalDiameter || 0.25

  // Structural pipe supports at intervals along the ground
  const groundSupports = useMemo(() => {
    const supports: [number, number, number][] = []
    route.waypoints.forEach((wp, i) => {
      // If waypoint is elevated above ground (> 1.0) and not first/last
      if (wp[1] > 1.0 && i > 0 && i < route.waypoints.length - 1) {
        supports.push([wp[0], wp[1] / 2, wp[2]])
      }
    })
    return supports
  }, [route.waypoints])

  return (
    <group>
      {/* Structural Support Stanchions */}
      {groundSupports.map((sp, idx) => (
        <group key={idx} position={sp}>
          <mesh>
            <boxGeometry args={[0.3, sp[1] * 2, 0.3]} />
            <meshStandardMaterial color="#334155" metalness={0.6} roughness={0.6} />
          </mesh>
          {/* Top Cradle */}
          <mesh position={[0, sp[1], 0]}>
            <boxGeometry args={[0.8, 0.1, 0.5]} />
            <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.4} />
          </mesh>
        </group>
      ))}

      {/* Main Pipe Tube Geometry */}
      <mesh castShadow receiveShadow>
        <tubeGeometry args={[curve, tubularSegments, pipeRadius, 10, false]} />
        <meshStandardMaterial
          color={isSelected ? '#38bdf8' : '#475569'}
          metalness={0.75}
          roughness={0.25}
        />
      </mesh>

      {/* Flow Indicator Particles along the line */}
      <FlowParticles
        curve={curve}
        flowRate={route.flowRate}
        color={fluidInfo.hex}
        particleCount={Math.max(8, route.waypoints.length * 3)}
        radius={pipeRadius * 0.7}
      />
    </group>
  )
}
