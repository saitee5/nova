import { BayDefinition } from '../types'

export const PLANT_BAYS: BayDefinition[] = [
  {
    id: 'bay-1',
    code: 'Bay 1',
    name: 'Feed & Preheat',
    subtitle: 'Feed pumps, preheater, feed surge drum & dilution steam mixing',
    colorTheme: '#22c55e', // Emerald / Green
    accentColor: '#4ade80',
    position: [-85, 0, -10],
    size: [34, 30],
    cameraFocusPoint: {
      position: [-85, 24, 24],
      target: [-85, 0, -10],
    },
  },
  {
    id: 'bay-2',
    code: 'Bay 2',
    name: 'Cracking Furnaces',
    subtitle: 'Hero Bay — Pyrolysis furnaces F-201A/B/C with 4 ML predictive models',
    colorTheme: '#f43f5e', // Hero Rose / Ruby
    accentColor: '#fb7185',
    position: [-38, 0, -10],
    size: [50, 36], // Larger footprint for Hero Bay
    cameraFocusPoint: {
      position: [-42, 18, 16], // Frames F-201A specifically
      target: [-42, 4.0, -10],
    },
  },
  {
    id: 'bay-3',
    code: 'Bay 3',
    name: 'Transfer & Quench',
    subtitle: 'Transfer line exchanger TLE-201, quench tower T-101 & quench circulation',
    colorTheme: '#3b82f6', // Sapphire Blue
    accentColor: '#60a5fa',
    position: [12, 0, -10],
    size: [34, 30],
    cameraFocusPoint: {
      position: [12, 26, 26],
      target: [12, 0, -10],
    },
  },
  {
    id: 'bay-4',
    code: 'Bay 4',
    name: 'Compression & Separation',
    subtitle: 'Cracked gas compressors C-101/C-102, knockout drum & fractionators',
    colorTheme: '#eab308', // Amber / Gold
    accentColor: '#fde047',
    position: [54, 0, -10],
    size: [38, 30],
    cameraFocusPoint: {
      position: [54, 28, 26],
      target: [54, 0, -10],
    },
  },
  {
    id: 'bay-5',
    code: 'Bay 5',
    name: 'Utilities & Safety',
    subtitle: 'Fuel gas, steam headers, cooling water, ESD valves, gas detection & flare',
    colorTheme: '#a855f7', // Purple
    accentColor: '#c084fc',
    position: [96, 0, -10],
    size: [36, 30],
    cameraFocusPoint: {
      position: [96, 26, 26],
      target: [96, 0, -10],
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
