"""
backend/config_reference_plant.py — Reference Petrochemical Plant Configuration.

Defines the reference Ethylene Steam Cracker plant layout and equipment catalog:
- F-201A: Steam Cracker Furnace
- E-201: Transfer-Line Exchanger
- K-201: Cracked Gas Compressor
- V-201: Separator / Process Vessel
- P-201A / P-201B: Process & Standby Pumps
- T-201: Storage Tank
- Fuel Gas System, Flare System, Fire & Gas System, Utilities

Note: Simulated benchmark reference plant for testing and development.
"""
from __future__ import annotations

from typing import Any, Dict, List
from backend.models.industrial_domain import Asset, Equipment, Plant, RiskTier, Unit

REFERENCE_PLANT = Plant(
    plant_id="PLANT-ETH-01",
    name="NOVA Reference Ethylene Plant",
    location="Simulated Petrochemical Complex",
    units=["UNIT-CRACK-01", "UNIT-RECOV-01", "UNIT-UTIL-01"],
)

REFERENCE_UNITS = [
    Unit(
        unit_id="UNIT-CRACK-01",
        plant_id="PLANT-ETH-01",
        name="Pyrolysis & Steam Cracking Unit",
        unit_type="Ethylene Steam Cracking",
        assets=["F-201A", "E-201", "K-201", "V-201", "P-201A", "P-201B", "T-201"],
    ),
    Unit(
        unit_id="UNIT-SAFETY-01",
        plant_id="PLANT-ETH-01",
        name="Safety & Auxiliary Systems",
        unit_type="Safety & Utilities",
        assets=["SYS-FUEL-GAS", "SYS-FLARE", "SYS-FNG"],
    ),
]

REFERENCE_ASSETS: List[Dict[str, Any]] = [
    {
        "asset_id": "F-201A",
        "unit_id": "UNIT-CRACK-01",
        "name": "Steam Cracker Furnace F-201A",
        "asset_class": "Furnace",
        "criticality": "CRITICAL",
        "description": "Naphtha/Gas cracking furnace equipped with coil outlet temperature (COT) controls.",
        "key_tags": ["TI-20101", "TI-20102", "FI-20105", "PI-20110"],
    },
    {
        "asset_id": "E-201",
        "unit_id": "UNIT-CRACK-01",
        "name": "Transfer-Line Exchanger E-201",
        "asset_class": "HeatExchanger",
        "criticality": "HIGH",
        "description": "Quenches furnace effluent to generate high-pressure steam.",
        "key_tags": ["TI-20120", "PI-20125"],
    },
    {
        "asset_id": "K-201",
        "unit_id": "UNIT-CRACK-01",
        "name": "Cracked Gas Compressor K-201",
        "asset_class": "Compressor",
        "criticality": "CRITICAL",
        "description": "Multi-stage centrifugal cracked gas compressor driven by steam turbine.",
        "key_tags": ["VI-20150", "TI-20155", "PI-20160"],
    },
    {
        "asset_id": "V-201",
        "unit_id": "UNIT-CRACK-01",
        "name": "Separator / Process Vessel V-201",
        "asset_class": "Vessel",
        "criticality": "HIGH",
        "description": "High-pressure hydrocarbon knock-out drum.",
        "key_tags": ["LI-20170", "PI-20175"],
    },
    {
        "asset_id": "P-201A",
        "unit_id": "UNIT-CRACK-01",
        "name": "Process Hydrocarbon Pump P-201A",
        "asset_class": "Pump",
        "criticality": "HIGH",
        "description": "Primary hydrocarbon circulation pump.",
        "key_tags": ["FI-20180", "VI-20182"],
    },
    {
        "asset_id": "P-201B",
        "unit_id": "UNIT-CRACK-01",
        "name": "Standby Hydrocarbon Pump P-201B",
        "asset_class": "Pump",
        "criticality": "MEDIUM",
        "description": "Auto-start standby circulation pump.",
        "key_tags": ["FI-20185", "VI-20187"],
    },
    {
        "asset_id": "T-201",
        "unit_id": "UNIT-CRACK-01",
        "name": "Pyrolysis Gasoline Storage Tank T-201",
        "asset_class": "Tank",
        "criticality": "MEDIUM",
        "description": "Atmospheric storage tank for liquid hydrocarbon intermediate.",
        "key_tags": ["LI-20190", "TI-20192"],
    },
    {
        "asset_id": "SYS-FUEL-GAS",
        "unit_id": "UNIT-SAFETY-01",
        "name": "Fuel Gas Supply System",
        "asset_class": "FuelGasSystem",
        "criticality": "CRITICAL",
        "description": "Header supplying fuel gas to furnace burners.",
        "key_tags": ["PI-20001", "FI-20002"],
    },
    {
        "asset_id": "SYS-FLARE",
        "unit_id": "UNIT-SAFETY-01",
        "name": "Elevated Emergency Flare System",
        "asset_class": "Flare",
        "criticality": "CRITICAL",
        "description": "Overpressure relief and safe emergency combustion stack.",
        "key_tags": ["FI-20010", "TI-20012"],
    },
    {
        "asset_id": "SYS-FNG",
        "unit_id": "UNIT-SAFETY-01",
        "name": "Fire & Gas Detection System",
        "asset_class": "FireAndGas",
        "criticality": "CRITICAL",
        "description": "Distributed optical flame detectors and toxic/flammable gas sensors.",
        "key_tags": ["GD-20050", "FD-20055"],
    },
]


def get_reference_plant_summary() -> Dict[str, Any]:
    """Return dictionary summary of reference plant hierarchy."""
    return {
        "plant": REFERENCE_PLANT.model_dump(),
        "units": [u.model_dump() for u in REFERENCE_UNITS],
        "assets": REFERENCE_ASSETS,
        "total_assets": len(REFERENCE_ASSETS),
    }
