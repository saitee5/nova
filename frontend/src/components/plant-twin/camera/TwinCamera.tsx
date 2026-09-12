import React, { useRef, useEffect } from 'react'
import * as THREE from 'three'
import { useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useTwinStore } from '../store/useTwinStore'

const OVERVIEW_POS = new THREE.Vector3(0, 115, 130)
const OVERVIEW_TARGET = new THREE.Vector3(0, 0, 5)

export const TwinCamera: React.FC = () => {
  const { camera } = useThree()
  const controlsRef = useRef<any>(null)

  const selectedBayId = useTwinStore((s) => s.selectedBayId)
  const selectedEquipmentId = useTwinStore((s) => s.selectedEquipmentId)
  const cameraMode = useTwinStore((s) => s.cameraMode)
  const bays = useTwinStore((s) => s.bays)
  const equipmentList = useTwinStore((s) => s.equipmentList)

  // Current desired target positions for lerping
  const desiredPos = useRef<THREE.Vector3>(OVERVIEW_POS.clone())
  const desiredTarget = useRef<THREE.Vector3>(OVERVIEW_TARGET.clone())
  const isAnimating = useRef<boolean>(false)

  // Recalculate camera destination whenever selection or mode changes
  useEffect(() => {
    if (cameraMode === 'overview' || (!selectedBayId && !selectedEquipmentId)) {
      desiredPos.current.copy(OVERVIEW_POS)
      desiredTarget.current.copy(OVERVIEW_TARGET)
      isAnimating.current = true
      return
    }

    // When in bay inspection mode, frame the specific bay
    if (cameraMode === 'bay' && selectedBayId) {
      const bay = bays.find((b) => b.id === selectedBayId)
      if (bay) {
        desiredPos.current.set(...bay.cameraFocusPoint.position)
        desiredTarget.current.set(...bay.cameraFocusPoint.target)
        isAnimating.current = true
        return
      }
    }

    // When inspecting specific machinery closely
    if (cameraMode === 'equipment' && selectedEquipmentId) {
      const eq = equipmentList.find((e) => e.id === selectedEquipmentId)
      if (eq) {
        desiredTarget.current.set(eq.position[0], eq.position[1] + 2.5, eq.position[2])
        desiredPos.current.set(
          eq.position[0] + 6,
          eq.position[1] + 16,
          eq.position[2] + 20
        )
        isAnimating.current = true
        return
      }
    }

    // Default fallback: focus bay first if set, otherwise equipment
    if (selectedBayId) {
      const bay = bays.find((b) => b.id === selectedBayId)
      if (bay) {
        desiredPos.current.set(...bay.cameraFocusPoint.position)
        desiredTarget.current.set(...bay.cameraFocusPoint.target)
        isAnimating.current = true
        return
      }
    }

    if (selectedEquipmentId) {
      const eq = equipmentList.find((e) => e.id === selectedEquipmentId)
      if (eq) {
        desiredTarget.current.set(eq.position[0], eq.position[1] + 2.5, eq.position[2])
        desiredPos.current.set(
          eq.position[0] + 6,
          eq.position[1] + 16,
          eq.position[2] + 20
        )
        isAnimating.current = true
      }
    }
  }, [selectedBayId, selectedEquipmentId, cameraMode, bays, equipmentList])

  useFrame(() => {
    if (!isAnimating.current) return

    // Smooth lerp camera position
    camera.position.lerp(desiredPos.current, 0.065)

    // Smooth lerp orbit controls target
    if (controlsRef.current) {
      controlsRef.current.target.lerp(desiredTarget.current, 0.065)
      controlsRef.current.update()
    }

    // Stop animating once close enough
    const distPos = camera.position.distanceTo(desiredPos.current)
    const distTarget = controlsRef.current
      ? controlsRef.current.target.distanceTo(desiredTarget.current)
      : 0

    if (distPos < 0.1 && distTarget < 0.1) {
      isAnimating.current = false
    }
  })

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={15}
      maxDistance={320}
      maxPolarAngle={Math.PI / 2 - 0.05} // Don't allow camera below ground
    />
  )
}
