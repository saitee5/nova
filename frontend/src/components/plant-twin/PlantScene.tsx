import React from 'react'
import * as THREE from 'three'
import { useTwinStore } from './store/useTwinStore'
import { Furnace } from './equipment/Furnace'
import { Coil } from './equipment/Coil'
import { Tank } from './equipment/Tank'
import { Compressor } from './equipment/Compressor'
import { Column } from './equipment/Column'
import { HeatExchanger } from './equipment/HeatExchanger'
import { Pump } from './equipment/Pump'
import { Valve, InstancedValves } from './equipment/Valve'
import { PipeRoute } from './process/PipeRoute'
import { RiskIndicator } from './overlays/RiskIndicator'
import { AnomalyPulse } from './overlays/AnomalyPulse'
import { SensorMarker } from './overlays/SensorMarker'
import { EquipmentItem } from './types'

export const PlantScene: React.FC = () => {
  const bays = useTwinStore((s) => s.bays)
  const equipmentList = useTwinStore((s) => s.equipmentList)
  const pipeRoutes = useTwinStore((s) => s.pipeRoutes)
  const selectedBayId = useTwinStore((s) => s.selectedBayId)
  const selectedEquipmentId = useTwinStore((s) => s.selectedEquipmentId)
  const selectBay = useTwinStore((s) => s.selectBay)
  const selectEquipment = useTwinStore((s) => s.selectEquipment)

  // Positions for instanced small bypass/sample valves
  const sampleValvePositions: [number, number, number][] = [
    [-112, 0.4, -6],
    [-97, 0.4, 0],
    [-68, 0.4, -6],
    [-42, 0.4, -4],
    [5, 0.4, -6],
    [40, 0.4, -6],
    [80, 0.4, -6],
    [100, 0.4, 0],
  ]

  // Render individual equipment matching its type
  const renderEquipment = (item: EquipmentItem) => {
    const isSelected = item.id === selectedEquipmentId
    const handleClick = () => {
      selectEquipment(item.id)
    }

    let Component: React.FC<any> = Tank
    switch (item.type) {
      case 'furnace':
        Component = Furnace
        break
      case 'coil':
        Component = Coil
        break
      case 'column':
        Component = Column
        break
      case 'compressor':
        Component = Compressor
        break
      case 'heatExchanger':
        Component = HeatExchanger
        break
      case 'pump':
        Component = Pump
        break
      case 'valve':
        Component = Valve
        break
      case 'tank':
      default:
        Component = Tank
        break
    }

    return (
      <group key={item.id}>
        <Component
          equipment={item}
          isSelected={isSelected}
          onClick={handleClick}
        />
        {/* Risk Badge overlay */}
        <RiskIndicator equipment={item} />
        {/* Anomaly Ring/Beacon pulse overlay */}
        <AnomalyPulse equipment={item} />
      </group>
    )
  }

  return (
    <group>
      {/* ─── GROUND BASE & PLANT PLAZA ──────────────────────────── */}
      {/* Main Ground Slab (Light Concrete Pad) */}
      <mesh position={[0, -0.2, 8]} receiveShadow>
        <boxGeometry args={[270, 0.4, 100]} />
        <meshStandardMaterial color="#E2E8F0" roughness={0.85} metalness={0.05} />
      </mesh>

      {/* Perimeter Roads & Asphalt Corridors */}
      {/* Central E-W Avenue between Upper Bays and Lower Facilities */}
      <mesh position={[0, 0.02, 10]} receiveShadow>
        <planeGeometry args={[260, 8]} />
        <meshStandardMaterial color="#94A3B8" roughness={0.7} />
      </mesh>
      {/* Road Center Dotted Line */}
      <mesh position={[0, 0.03, 10]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[250, 0.2]} />
        <meshBasicMaterial color="#FFFFFF" transparent opacity={0.7} />
      </mesh>

      {/* ─── 6 BAYS PLATFORMS & LABELED ZONES ─────────────────────── */}
      {bays.map((bay) => {
        const isBaySelected = bay.id === selectedBayId
        return (
          <group key={bay.id} position={bay.position}>
            {/* Concrete Pad Foundation for Bay */}
            <mesh
              position={[0, 0.05, 0]}
              receiveShadow
              onClick={(e) => {
                e.stopPropagation()
                selectBay(bay.id)
              }}
              onPointerOver={() => {
                document.body.style.cursor = 'pointer'
              }}
              onPointerOut={() => {
                document.body.style.cursor = 'auto'
              }}
            >
              <boxGeometry args={[bay.size[0], 0.1, bay.size[1]]} />
              <meshStandardMaterial
                color={isBaySelected ? '#FFFFFF' : '#F8FAFC'}
                roughness={0.8}
              />
            </mesh>

            {/* Color-Coded Bay Boundary Border */}
            <mesh
              position={[0, 0.12, 0]}
              rotation={[-Math.PI / 2, 0, 0]}
              onClick={(e) => {
                e.stopPropagation()
                selectBay(bay.id)
              }}
            >
              <planeGeometry args={[bay.size[0], bay.size[1]]} />
              <meshBasicMaterial
                color={bay.colorTheme}
                transparent
                opacity={isBaySelected ? 0.22 : 0.12}
                depthWrite={false}
              />
            </mesh>

            {/* Bay Border Outline Strip */}
            <lineSegments position={[0, 0.14, 0]}>
              <edgesGeometry
                args={[new THREE.BoxGeometry(bay.size[0], 0.1, bay.size[1])]}
              />
              <lineBasicMaterial
                color={bay.colorTheme}
                linewidth={isBaySelected ? 2 : 1}
                transparent
                opacity={isBaySelected ? 0.95 : 0.7}
              />
            </lineSegments>

            {/* Bay Label Plaque on Floor */}
            <group position={[0, 0.15, bay.size[1] / 2 - 2.5]}>
              <mesh rotation={[-Math.PI / 2, 0, 0]}>
                <planeGeometry args={[bay.size[0] * 0.8, 2.2]} />
                <meshBasicMaterial color="#FFFFFF" transparent opacity={0.9} />
              </mesh>
            </group>
          </group>
        )
      })}

      {/* ─── PERIMETER / OFFSITE FACILITIES (LOWER HALF OF REFERENCE) ─── */}
      {/* Control Room & Administration */}
      <group position={[-84, 0, 24]}>
        <mesh position={[0, 2.0, 0]} castShadow receiveShadow>
          <boxGeometry args={[26, 4.0, 12]} />
          <meshStandardMaterial color="#334155" metalness={0.4} roughness={0.6} />
        </mesh>
        {/* Glass Windows Ribbon */}
        <mesh position={[0, 2.5, 6.05]}>
          <boxGeometry args={[24, 1.4, 0.1]} />
          <meshStandardMaterial color="#38bdf8" metalness={0.9} roughness={0.1} />
        </mesh>
      </group>

      {/* Waste Treatment (ETP) Basin */}
      <group position={[-20, 0, 24]}>
        <mesh position={[0, 0.8, 0]} receiveShadow>
          <boxGeometry args={[28, 1.6, 12]} />
          <meshStandardMaterial color="#1e293b" roughness={0.9} />
        </mesh>
        {/* Water Surface in Aeration Basin */}
        <mesh position={[0, 1.5, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[26, 10]} />
          <meshStandardMaterial
            color="#0d9488"
            metalness={0.8}
            roughness={0.2}
            transparent
            opacity={0.85}
          />
        </mesh>
      </group>

      {/* Flare System */}
      <group position={[30, 0, 24]}>
        <mesh position={[0, 0.3, 0]}>
          <cylinderGeometry args={[2.5, 2.8, 0.6, 16]} />
          <meshStandardMaterial color="#1e293b" roughness={0.9} />
        </mesh>
        {/* Tall Flare Stack Tower */}
        <mesh position={[0, 12.0, 0]} castShadow>
          <cylinderGeometry args={[0.5, 0.8, 24, 16]} />
          <meshStandardMaterial color="#64748b" metalness={0.8} roughness={0.2} />
        </mesh>
        {/* Flare Flame at Tip */}
        <mesh position={[0, 25.2, 0]}>
          <coneGeometry args={[0.9, 2.6, 12]} />
          <meshBasicMaterial color="#f97316" />
        </mesh>
        {/* Point Light for Flare Glow */}
        <pointLight position={[0, 26.0, 0]} color="#f97316" intensity={2.5} distance={45} />
      </group>

      {/* Fire Water System (Red Tanks) */}
      <group position={[76, 0, 24]}>
        <mesh position={[0, 0.2, 0]}>
          <boxGeometry args={[24, 0.4, 12]} />
          <meshStandardMaterial color="#1e293b" roughness={0.9} />
        </mesh>
        {/* Tank 1 */}
        <mesh position={[-5, 3.5, 0]} castShadow>
          <cylinderGeometry args={[4.2, 4.2, 6.5, 20]} />
          <meshStandardMaterial color="#b91c1c" metalness={0.5} roughness={0.4} />
        </mesh>
        {/* Tank 2 */}
        <mesh position={[5, 3.5, 0]} castShadow>
          <cylinderGeometry args={[4.2, 4.2, 6.5, 20]} />
          <meshStandardMaterial color="#b91c1c" metalness={0.5} roughness={0.4} />
        </mesh>
      </group>

      {/* ─── EQUIPMENT ACROSS ALL 6 BAYS ────────────────────────── */}
      {equipmentList.map(renderEquipment)}

      {/* ─── PROCESS PIPING ROUTES ──────────────────────────────── */}
      {pipeRoutes.map((route) => (
        <PipeRoute key={route.id} route={route} />
      ))}

      {/* ─── INSTANCED REPEAT VALVES ────────────────────────────── */}
      <InstancedValves positions={sampleValvePositions} />

      {/* ─── IN-SCENE SENSOR FIELD TRANSMITTERS ─────────────────── */}
      <SensorMarker position={[-88, 2.2, -4]} type="TT" status="normal" />
      <SensorMarker position={[-31, 8.2, -14]} type="TT" status="critical" />
      <SensorMarker position={[-15, 3.8, -2]} type="VT" status="critical" />
      <SensorMarker position={[30, 15.5, -14]} type="PT" status="warning" />
      <SensorMarker position={[95, 3.0, -14]} type="PT" status="normal" />
    </group>
  )
}
