import React, { useRef } from 'react'
import * as THREE from 'three'
import { EquipmentItem } from '../types'
import { getRiskState, RISK_COLORS } from '../utils/riskUtils'
import { useFrame } from '@react-three/fiber'

interface HeatExchangerProps {
  equipment: EquipmentItem
  isSelected?: boolean
  onClick?: (e: any) => void
}

export const HeatExchanger: React.FC<HeatExchangerProps> = ({ equipment, isSelected, onClick }) => {
  const groupRef = useRef<THREE.Group>(null)
  const shellMatRef = useRef<THREE.MeshStandardMaterial>(null)
  const isCoolingTower = equipment.tag.startsWith('CT-') || equipment.name.includes('Cooling Tower')

  const riskTier = getRiskState(equipment)
  const isHighOrCritical = riskTier === 'HIGH' || riskTier === 'CRITICAL'
  const isAlarm = equipment.status === 'alarm' || riskTier === 'CRITICAL'

  useFrame((state) => {
    if (shellMatRef.current && isHighOrCritical) {
      const speed = riskTier === 'CRITICAL' ? 8 : 4
      const pulse = (Math.sin(state.clock.elapsedTime * speed) + 1) * 0.5
      shellMatRef.current.emissiveIntensity = 0.3 + pulse * (riskTier === 'CRITICAL' ? 1.0 : 0.5)
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
      {/* Concrete Foundation */}
      <mesh position={[0, 0.2, 0]} receiveShadow>
        <boxGeometry args={[isCoolingTower ? 7.2 : 5.8, 0.4, isCoolingTower ? 5.2 : 3.2]} />
        <meshStandardMaterial color="#1e293b" roughness={0.9} />
      </mesh>

      {/* Selected Indicator */}
      {isSelected && (
        <mesh position={[0, 0.45, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[isCoolingTower ? 4.5 : 3.4, isCoolingTower ? 4.9 : 3.8, 24]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
      )}

      {isCoolingTower ? (
        // ── Induced Draft Cooling Tower Bank ──
        <group position={[0, 2.6, 0]}>
          <mesh castShadow receiveShadow>
            <boxGeometry args={[6.4, 4.4, 4.4]} />
            <meshStandardMaterial
              ref={shellMatRef}
              color={baseColor}
              metalness={0.4}
              roughness={0.6}
              emissive={emissiveColor}
              emissiveIntensity={isHighOrCritical ? 0.4 : 0}
            />
          </mesh>
          {/* Dual Top Fan Shrouds */}
          {[-1.6, 1.6].map((x, idx) => (
            <group key={idx} position={[x, 2.5, 0]}>
              <mesh>
                <cylinderGeometry args={[1.2, 1.35, 0.7, 16]} />
                <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.3} />
              </mesh>
              {/* Fan Hub */}
              <mesh position={[0, 0.2, 0]}>
                <cylinderGeometry args={[0.3, 0.3, 0.2, 12]} />
                <meshStandardMaterial color="#0f172a" />
              </mesh>
            </group>
          ))}
          {/* Louvered Air Inlets at Bottom */}
          <mesh position={[0, -1.3, 2.22]}>
            <boxGeometry args={[5.8, 1.4, 0.1]} />
            <meshStandardMaterial color="#1e293b" roughness={0.9} />
          </mesh>
        </group>
      ) : (
        // ── Shell-and-Tube Exchanger (TEMA Style) ──
        <group position={[0, 1.8, 0]}>
          {/* Twin Support Saddles */}
          {[-1.4, 1.4].map((x, idx) => (
            <mesh key={idx} position={[x, -0.9, 0]}>
              <boxGeometry args={[0.5, 1.4, 1.6]} />
              <meshStandardMaterial color="#334155" metalness={0.5} roughness={0.7} />
            </mesh>
          ))}

          {/* Main Cylindrical Shell */}
          <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
            <cylinderGeometry args={[1.0, 1.0, 4.2, 20]} />
            <meshStandardMaterial
              ref={shellMatRef}
              color={baseColor}
              metalness={0.7}
              roughness={0.3}
              emissive={emissiveColor}
              emissiveIntensity={isHighOrCritical ? 0.4 : 0}
            />
          </mesh>

          {/* Tubesheet Flanges */}
          {[-2.0, 2.0].map((x, idx) => (
            <mesh key={idx} position={[x, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[1.2, 1.2, 0.2, 20]} />
              <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.3} />
            </mesh>
          ))}

          {/* Channel Bonnet Head (Left) */}
          <mesh position={[-2.4, 0, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[1.0, 1.0, 0.7, 18]} />
            <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
          </mesh>

          {/* Floating Head Cover (Right Dome) */}
          <mesh position={[2.2, 0, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
            <sphereGeometry args={[1.0, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
            <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
          </mesh>

          {/* Top Nozzle with Flange */}
          <group position={[-0.8, 1.25, 0]}>
            <mesh>
              <cylinderGeometry args={[0.22, 0.22, 0.55, 12]} />
              <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
            </mesh>
            <mesh position={[0, 0.3, 0]}>
              <cylinderGeometry args={[0.35, 0.35, 0.1, 12]} />
              <meshStandardMaterial color="#64748b" metalness={0.9} roughness={0.2} />
            </mesh>
          </group>

          {/* Bottom Nozzle with Flange */}
          <group position={[0.8, -1.25, 0]}>
            <mesh>
              <cylinderGeometry args={[0.22, 0.22, 0.55, 12]} />
              <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
            </mesh>
          </group>
        </group>
      )}
    </group>
  )
}
