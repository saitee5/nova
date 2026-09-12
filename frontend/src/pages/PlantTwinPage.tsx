import React from 'react'
import { PlantTwinCanvas } from '../components/plant-twin/PlantTwinCanvas'
import Navbar from '../components/Navbar'

export const PlantTwinPage: React.FC = () => {
  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 overflow-hidden">
      <Navbar />
      <div className="flex-1 w-full h-full pt-16 relative">
        <PlantTwinCanvas />
      </div>
    </div>
  )
}

export default PlantTwinPage
