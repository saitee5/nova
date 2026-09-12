import { BayDefinition } from '../types'

export const PLANT_BAYS: BayDefinition[] = [
  {
    id: 'bay-1',
    code: 'Bay 1',
    name: 'Feedstock Receiving & Storage',
    subtitle: 'Crude oil & condensate storage, transfer pumps & surge drum',
    colorTheme: '#22c55e', // Emerald / Green
    accentColor: '#4ade80',
    position: [-105, 0, -10],
    size: [38, 32],
    cameraFocusPoint: {
      position: [-105, 26, 26],
      target: [-105, 0, -10],
    },
  },
  {
    id: 'bay-2',
    code: 'Bay 2',
    name: 'Pre-Treatment',
    subtitle: 'Desalting, drying, pre-flash column & pre-heaters',
    colorTheme: '#3b82f6', // Blue
    accentColor: '#60a5fa',
    position: [-63, 0, -10],
    size: [38, 32],
    cameraFocusPoint: {
      position: [-63, 26, 26],
      target: [-63, 0, -10],
    },
  },
  {
    id: 'bay-3',
    code: 'Bay 3',
    name: 'Cracking Unit',
    subtitle: 'Ethylene pyrolysis furnaces, radiant coils & quench tower',
    colorTheme: '#f43f5e', // Red / Rose Pink
    accentColor: '#fb7185',
    position: [-21, 0, -10],
    size: [38, 32],
    cameraFocusPoint: {
      position: [-21, 26, 26],
      target: [-21, 0, -10],
    },
  },
  {
    id: 'bay-4',
    code: 'Bay 4',
    name: 'Separation & Purification',
    subtitle: 'Demethanizer, deethanizer & fractionation towers',
    colorTheme: '#eab308', // Amber / Yellow
    accentColor: '#fde047',
    position: [21, 0, -10],
    size: [38, 32],
    cameraFocusPoint: {
      position: [21, 28, 26],
      target: [21, 0, -10],
    },
  },
  {
    id: 'bay-5',
    code: 'Bay 5',
    name: 'Utilities',
    subtitle: 'Cooling towers, steam boilers, plant air & nitrogen units',
    colorTheme: '#a855f7', // Purple
    accentColor: '#c084fc',
    position: [63, 0, -10],
    size: [38, 32],
    cameraFocusPoint: {
      position: [63, 26, 26],
      target: [63, 0, -10],
    },
  },
  {
    id: 'bay-6',
    code: 'Bay 6',
    name: 'Offsites & Storage',
    subtitle: 'Ethylene/propylene spheres, bullet vessels & effluent ponds',
    colorTheme: '#06b6d4', // Cyan / Teal
    accentColor: '#22d3ee',
    position: [105, 0, -10],
    size: [38, 32],
    cameraFocusPoint: {
      position: [105, 26, 26],
      target: [105, 0, -10],
    },
  },
]

export const PERIMETER_ZONES = [
  {
    id: 'ctrl-admin',
    name: 'Control Room & Administration',
    position: [-84, 0, 24] as [number, number, number],
    size: [48, 18] as [number, number],
    colorTheme: '#475569',
  },
  {
    id: 'etp',
    name: 'Waste Treatment (ETP)',
    position: [-20, 0, 24] as [number, number, number],
    size: [40, 18] as [number, number],
    colorTheme: '#0d9488',
  },
  {
    id: 'flare',
    name: 'Flare System',
    position: [30, 0, 24] as [number, number, number],
    size: [24, 18] as [number, number],
    colorTheme: '#ea580c',
  },
  {
    id: 'fire-water',
    name: 'Fire Water System',
    position: [76, 0, 24] as [number, number, number],
    size: [30, 18] as [number, number],
    colorTheme: '#dc2626',
  },
]
