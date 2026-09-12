import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface TankProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const Tank: React.FC<TankProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const isSphere = equipment.specs?.Type?.includes('Hortonsphere') || equipment.tag.startsWith('S-')
  const isBullet = equipment.name.includes('Vessel') || equipment.name.includes('Drum') || equipment.tag.startsWith('V-')
  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL'

  // Animate emissive pulse on high / critical
  const meshMaterialRef = useRef<THREE.MeshStandardMaterial>(null)
  useFrame((state) => {
    if (meshMaterialRef.current && isHighOrCritical) {
      const speed = riskTier === 'CRITICAL' ? 8 : 4
      const pulse = (Math.sin(state.clock.elapsedTime * speed) + 1) * 0.5
      meshMaterialRef.current.emissiveIntensity = 0.2 + pulse * (riskTier === 'CRITICAL' ? 0.9 : 0.4)
    }
  })

  const baseColor = isAlarm ? '#991b1b' : '#334155'
  const emissiveColor = isHighOrCritical ? RISK_COLORS[riskTier].threeHex : 0x000000

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
      {/* Foundation / Concrete ring pad */}
      <mesh position={[0, 0.15, 0]} receiveShadow>
        <cylinderGeometry args={[isSphere ? 4.2 : 5.8, isSphere ? 4.4 : 6.0, 0.3, 24]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Selected highlight ring */}
      {isSelected && (
        <mesh position={[0, 0.35, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[6.2, 6.7, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {isSphere ? (
        // ── Hortonsphere (Pressurized Spherical Tank) ──
        <group position={[0, 5.5, 0]}>
          <mesh castShadow receiveShadow>
            <sphereGeometry args={[4.2, 24, 20]} />
            <meshStandardMaterial
              ref={meshMaterialRef}
              color={baseColor}
              metalness={0.7}
              roughness={0.3}
              emissive={emissiveColor}
              emissiveIntensity={isHighOrCritical ? 0.5 : 0}
            />
          </mesh>
          {/* Support Legs */}
          {[0, 1, 2, 3, 4, 5].map((i) => {
            const angle = (i * Math.PI * 2) / 6
            const r = 3.6
            const x = Math.cos(angle) * r
            const z = Math.sin(angle) * r
            return (
              <group key={i} position={[x, -2.5, z]}>
                <mesh castShadow>
                  <cylinderGeometry args={[0.25, 0.25, 5.5, 8]} />
                  <meshStandardMaterial color="#475569" metalness={0.6} roughness={0.4} />
                </mesh>
                {/* Diagonal Bracing */}
                <mesh
                  position={[-x * 0.2, 0, -z * 0.2]}
                  rotation={[0, angle, Math.PI / 5]}
                >
                  <cylinderGeometry args={[0.08, 0.08, 5.2, 6]} />
                  <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.5} />
                </mesh>
              </group>
            )
          })}
          {/* Top walkway & vent */}
          <mesh position={[0, 4.3, 0]}>
            <cylinderGeometry args={[1.2, 1.2, 0.2, 12]} />
            <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.2} />
          </mesh>
          <mesh position={[0, 4.8, 0]}>
            <cylinderGeometry args={[0.15, 0.15, 0.8, 8]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.9} roughness={0.2} />
          </mesh>
        </group>
      ) : isBullet ? (
        // ── Horizontal Bullet Vessel / Drum ──
        <group position={[0, 2.5, 0]}>
          {/* Main horizontal cylinder */}
          <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
            <cylinderGeometry args={[1.8, 1.8, 6.0, 18]} />
            <meshStandardMaterial
              ref={meshMaterialRef}
              color={baseColor}
              metalness={0.65}
              roughness={0.35}
              emissive={emissiveColor}
              emissiveIntensity={isHighOrCritical ? 0.4 : 0}
            />
          </mesh>
          {/* Dished hemispherical heads */}
          <mesh position={[-3.0, 0, 0]} rotation={[0, -Math.PI / 2, 0]} castShadow>
            <sphereGeometry args={[1.8, 16, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
            <meshStandardMaterial color={baseColor} metalness={0.65} roughness={0.35} />
          </mesh>
          <mesh position={[3.0, 0, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
            <sphereGeometry args={[1.8, 16, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
            <meshStandardMaterial color={baseColor} metalness={0.65} roughness={0.35} />
          </mesh>
          {/* Twin Support Saddles */}
          {[-1.8, 1.8].map((x, idx) => (
            <mesh key={idx} position={[x, -1.3, 0]}>
              <boxGeometry args={[0.8, 2.2, 2.6]} />
              <meshStandardMaterial color="#334155" metalness={0.4} roughness={0.8} />
            </mesh>
          ))}
          {/* Top Nozzles & Relief Valve */}
          <mesh position={[0, 2.1, 0]}>
            <cylinderGeometry args={[0.2, 0.2, 0.6, 8]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
          </mesh>
        </group>
      ) : (
        // ── Large Cylindrical Storage Tank ──
        <group position={[0, 3.2, 0]}>
          {/* Shell */}
          <mesh castShadow receiveShadow>
            <cylinderGeometry args={[4.8, 4.8, 6.0, 24]} />
            <meshStandardMaterial
              ref={meshMaterialRef}
              color={baseColor}
              metalness={0.6}
              roughness={0.4}
              emissive={emissiveColor}
              emissiveIntensity={isHighOrCritical ? 0.4 : 0}
            />
          </mesh>
          {/* Roof (Dome / Cone) */}
          <mesh position={[0, 3.4, 0]} castShadow>
            <coneGeometry args={[4.9, 1.0, 24]} />
            <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
          </mesh>
          {/* Wind Girders / Rings */}
          <mesh position={[0, 1.2, 0]}>
            <torusGeometry args={[4.88, 0.08, 6, 24]} />
            <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
          </mesh>
          <mesh position={[0, -1.2, 0]}>
            <torusGeometry args={[4.88, 0.08, 6, 24]} />
            <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
          </mesh>
          {/* Top Vent & Radar Gauge */}
          <mesh position={[1.5, 4.0, 0]}>
            <cylinderGeometry args={[0.2, 0.2, 0.6, 8]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
          </mesh>
        </group>
      )}

      {/* Equipment Tag Label on Base */}
      <mesh position={[0, 0.6, isSphere ? 3.5 : isBullet ? 2.0 : 4.6]}>
        <boxGeometry args={[1.8, 0.4, 0.1]} />
        <meshBasicMaterial color="#0f172a" />
      </mesh>
    </group>
  )
}
