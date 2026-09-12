import React from 'react'
import { PlantTwinCanvas } from '../components/plant-twin/PlantTwinCanvas'

export const DigitalTwinPage: React.FC = () => {
  return (
    <div className="h-[calc(100vh-56px-48px)] w-full rounded-xl overflow-hidden border border-slate-200 shadow-sm bg-slate-100 relative">
      <PlantTwinCanvas />
    </div>
  )
}

export default DigitalTwinPage
