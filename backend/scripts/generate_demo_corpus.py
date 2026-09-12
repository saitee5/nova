"""
backend/scripts/generate_demo_corpus.py — Generates the 25 synthetic demo engineering documents in data/knowledge/demo.
"""
from __future__ import annotations
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = REPO_ROOT / "data" / "knowledge" / "demo"

DOCUMENTS = [
    {
        "filename": "doc_demo_sop_f201_001.md",
        "doc_id": "DOC-DEMO-SOP-F201-001",
        "title": "Normal Operating Envelope and Coil Outlet Temperature (COT) Control",
        "doc_type": "sop",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# SOP-F201-001: Normal Operating Envelope and Coil Outlet Temperature (COT) Control

## 1.0 PURPOSE & SCOPE
This standard operating procedure establishes baseline operational envelopes for Cracking Furnace F-201A in UNIT-CRACK-01.

## 2.0 NORMAL OPERATING ENVELOPE
- Target Coil Outlet Temperature (COT): 840.0 °C to 860.0 °C
- Normal Hydrocarbon Feed Rate: 24,000 kg/h
- Fuel Gas Header Pressure: 0.30 MPa via control valve FV-201
- Furnace Firebox Draft Pressure: -30.0 Pa draft

## 3.0 COT CONTROL AND FUEL GAS ADJUSTMENT
The operator shall monitor temperature transmitter TI-201. Firing adjustments are executed by modulating fuel gas valve FV-201 in coordination with combustion air dampers to maintain fuel gas combustion efficiency and draft stability.
""",
    },
    {
        "filename": "doc_demo_alm_f201_002.md",
        "doc_id": "DOC-DEMO-ALM-F201-002",
        "title": "High COT Alarm Response Procedure",
        "doc_type": "alarm_procedure",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# ALM-F201-002: High COT Alarm Response Procedure

## 1.0 ALARM SETPOINTS
- Alarm High (TI-201-AH): 885.0 °C
- Trip High-High (TI-201-TRIP): 895.0 °C

## 2.0 IMMEDIATE OPERATOR ACTIONS
When high COT alarm TI-201-AH activates:
1. Immediately verify fuel gas control valve FV-201 position and fuel gas header pressure.
2. Throttle firing by reducing FV-201 demand to trim excessive heat input.
3. Check dilution steam ratio and verify draft pressure before adjusting individual burners.
4. Notify Shift Supervisor and monitor radiant coil temperatures closely.
""",
    },
    {
        "filename": "doc_demo_alm_f201_003.md",
        "doc_id": "DOC-DEMO-ALM-F201-003",
        "title": "Low COT Alarm Response & Quench Protection",
        "doc_type": "alarm_procedure",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# ALM-F201-003: Low COT Alarm Response & Quench Protection

## 1.0 ALARM CONDITION
Low COT alarm activates if coil temperature falls below 820.0 °C on furnace F-201A.

## 2.0 QUENCH PROTECTION
Prevent hydrocarbon condensation and secondary reaction fouling in downstream quench exchangers by adjusting firing or reducing feed rate.
""",
    },
    {
        "filename": "doc_demo_sop_f201_004.md",
        "doc_id": "DOC-DEMO-SOP-F201-004",
        "title": "Startup & Burner Firing Sequence",
        "doc_type": "sop",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# SOP-F201-004: Startup & Burner Firing Sequence

## 1.0 SCOPE
Mandatory startup and burner firing sequence for Cracking Furnace F-201A.

## 2.0 PROCEDURE
1. Purge firebox with combustion air fan for 15 minutes minimum.
2. Verify pilot gas pressure and ignite pilots in alternating quadrants.
3. Gradually ramp firing to achieve steady thermal expansion rate < 50 °C/h.
""",
    },
    {
        "filename": "doc_demo_sop_f201_005.md",
        "doc_id": "DOC-DEMO-SOP-F201-005",
        "title": "Emergency Furnace Shutdown (ESD-1) Protocol",
        "doc_type": "emergency_procedure",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# SOP-F201-005: Emergency Furnace Shutdown (ESD-1) Protocol

## 1.0 EMERGENCY CONDITIONS
Emergency shutdown ESD protocol triggers on catastrophic tube rupture or severe overtemperature.

## 2.0 EXECUTION
Trip fuel gas main isolation valve, purge coils with dilution steam, and isolate hydrocarbon feed to F-201A.
""",
    },
    {
        "filename": "doc_demo_eng_f201_006.md",
        "doc_id": "DOC-DEMO-ENG-F201-006",
        "title": "Steam Dilution Ratio & Severity Control",
        "doc_type": "engineering_document",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# ENG-F201-006: Steam Dilution Ratio & Severity Control

## 1.0 SPECIFICATION
Engineering specification for steam dilution ratio on pyrolysis furnace F-201A.
Maintains steam-to-hydrocarbon ratio between 0.35 and 0.45 kg steam / kg feed to suppress coke deposition and optimize reaction severity.
""",
    },
    {
        "filename": "doc_demo_opm_f201_007.md",
        "doc_id": "DOC-DEMO-OPM-F201-007",
        "title": "Tube Metal Temperature (TMT) & Skin Thermocouples",
        "doc_type": "operating_manual",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# OPM-F201-007: Tube Metal Temperature (TMT) & Skin Thermocouples

## 1.0 TMT SURVEILLANCE
Tube Metal Temperature (TMT) is monitored continuously using welded skin thermocouples and optical pyrometers across Radiant Pass 1 through Pass 4.

## 2.0 OPERATING BOUNDARIES
- Normal Operating TMT: 930.0 °C to 980.0 °C
- Maximum Skin Thermocouple Alarm: 1040.0 °C
- Trip Threshold: 1080.0 °C
""",
    },
    {
        "filename": "doc_demo_opm_flt_008.md",
        "doc_id": "DOC-DEMO-OPM-FLT-008",
        "title": "Fuel Gas Pressure Drift & Valve Response",
        "doc_type": "operating_manual",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# OPM-FLT-008: Fuel Gas Pressure Drift & Valve Response

## 1.0 SYMPTOMS OF PRESSURE DRIFT
Uncontrolled drift in fuel gas header pressure causes erratic valve hunting on FV-201 and flame instability, leading to firebox draft pressure fluctuations.

## 2.0 MITIGATION
Inspect fuel gas pressure transmitter PI-201, verify supply regulator balance, and adjust FV-201 control loop tuning to restore stable draft and uniform heat distribution.
""",
    },
    {
        "filename": "doc_demo_opm_flt_009.md",
        "doc_id": "DOC-DEMO-OPM-FLT-009",
        "title": "Feed Flow Variance & Steam Disruption",
        "doc_type": "operating_manual",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# OPM-FLT-009: Feed Flow Variance & Steam Disruption

## 1.0 DISRUPTIONS
Sudden feed flow variance or dilution steam disruption rapidly alters furnace thermal balance on F-201A.
Immediate trimming of firing rate is mandatory to prevent local hot spots.
""",
    },
    {
        "filename": "doc_demo_eng_flt_010.md",
        "doc_id": "DOC-DEMO-ENG-FLT-010",
        "title": "Sensor Drift & Redundant Thermocouple Validation",
        "doc_type": "engineering_document",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# ENG-FLT-010: Sensor Drift & Redundant Thermocouple Validation

## 1.0 REDUNDANT 2oo3 VOTING
To distinguish genuine process thermal upset from sensor transmitter drift, F-201A utilizes triple-redundant thermocouples (2oo3 voting logic).

## 2.0 STATISTICAL DRIFT IDENTIFICATION
A temperature rate of change exceeding 5.0 °C/min without cross-correlation to fuel pressure or firebox draft indicates instrument drift or transmitter fault rather than a process runaway.
""",
    },
    {
        "filename": "doc_demo_saf_gen_011.md",
        "doc_id": "DOC-DEMO-SAF-GEN-011",
        "title": "Gas Detection Response Protocol",
        "doc_type": "safety_procedure",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# SAF-GEN-011: Gas Detection Response Protocol

## 1.0 GAS DETECTION THRESHOLDS
- 20% LEL: Advisory warning alarm; personnel investigate leak origin.
- 40% LEL: Critical alarm; immediate area evacuation and immediate cessation of all hot work permits.

## 2.0 PROTOCOL
Activate emergency ventilation and water deluge in affected bay upon confirmed combustible gas detection.
""",
    },
    {
        "filename": "doc_demo_saf_gen_012.md",
        "doc_id": "DOC-DEMO-SAF-GEN-012",
        "title": "Lockout / Tagout (LOTO) & Energy Isolation",
        "doc_type": "safety_procedure",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# SAF-GEN-012: Lockout / Tagout (LOTO) & Energy Isolation

## 1.0 ZERO-ENERGY STATE PRINCIPLE
Prior to performing maintenance on F-201A, all energy sources must be isolated to achieve a verified zero-energy state.

## 2.0 ISOLATION PROTOCOLS
1. Insert physical spectacle blind plates on fuel gas lines.
2. Apply lockout tagout (LOTO) padlocks on electrical switchgear at 480V MCC.
3. Vent and purge hydrocarbon lines with nitrogen before breaking containment.
""",
    },
    {
        "filename": "doc_demo_saf_gen_013.md",
        "doc_id": "DOC-DEMO-SAF-GEN-013",
        "title": "PPE & High-Temperature Zone Protocols",
        "doc_type": "safety_procedure",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# SAF-GEN-013: PPE & High-Temperature Zone Protocols

## 1.0 MANDATORY PPE
Entry into Cracking Furnace F-201A firing floor requires specific personal protective equipment (PPE):
- Aluminized thermal proximity suit and heat-resistant gloves
- Full-face tinted heat shield
- Portable 4-gas detector and safety glasses

## 2.0 SAFETY REQUIREMENTS
No lone working permitted inside high-temperature radiant zones.
""",
    },
    {
        "filename": "doc_demo_emg_gen_014.md",
        "doc_id": "DOC-DEMO-EMG-GEN-014",
        "title": "Unit Emergency Depressurization (EDP) & Flare Routing",
        "doc_type": "emergency_procedure",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# EMG-GEN-014: Unit Emergency Depressurization (EDP) & Flare Routing

## 1.0 EDP ACTIVATION
Initiate emergency depressurization (EDP) to route cracking coil inventory safely to the flare header during uncontrolled fire or high-pressure rupture risk.
""",
    },
    {
        "filename": "doc_demo_dat_f201_015.md",
        "doc_id": "DOC-DEMO-DAT-F201-015",
        "title": "Pyrolysis Cracking Furnace F-201A Engineering Datasheet",
        "doc_type": "equipment_datasheet",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# DAT-F201-015: Pyrolysis Cracking Furnace F-201A Engineering Datasheet

## 1.0 ASSET IDENTIFICATION
- Equipment ID: F-201A
- Equipment Name: Cracking Furnace F-201A (Radiant Pyrolysis)
- Unit Area: UNIT-CRACK-01

## 2.0 DESIGN RATINGS
- Normal Operating COT: 840.0 °C to 860.0 °C
- Normal Feed Throughput: 24,000 kg/h
- Design Maximum Tube Metal Temperature (TMT): 1080.0 °C
- Number of Radiant Passes: 4 passes in parallel
""",
    },
    {
        "filename": "doc_demo_dat_p101_016.md",
        "doc_id": "DOC-DEMO-DAT-P101-016",
        "title": "Hydrocarbon Feed Pumps P-101A/B Datasheet",
        "doc_type": "equipment_datasheet",
        "equipment_id": "P-101A",
        "equipment_type": "pump",
        "unit_area": "UNIT-CRACK-01",
        "content": """# DAT-P101-016: Hydrocarbon Feed Pumps P-101A/B Datasheet

## 1.0 SPECIFICATIONS
- Equipment ID: P-101A
- Equipment Type: Centrifugal Feed Pump
- Rated Capacity: 45.0 m3/h feed delivery specs
- Suction Pressure: 0.25 MPa; Discharge: 0.55 MPa
""",
    },
    {
        "filename": "doc_demo_pid_top_017.md",
        "doc_id": "DOC-DEMO-PID-TOP-017",
        "title": "UNIT-CRACK-01 Process Stream Topology",
        "doc_type": "pid",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# PID-TOP-017: UNIT-CRACK-01 Process Stream Topology

## 1.0 STREAM FLOW TOPOLOGY
Cracking furnace F-201A receives naphtha feed upstream from pumps P-101A and P-101B through separator V-201A.
Effluent from F-201A flows directly downstream to:
1. TLE-201 (Transfer Line Exchanger) for immediate effluent rapid quench.
2. Fractionator column T-101 for heavy end separation.
3. Cracked Gas Compressor C-101 (4-Stage centrifugal compressor) for downstream gas compression.
""",
    },
    {
        "filename": "doc_demo_mnt_f201_018.md",
        "doc_id": "DOC-DEMO-MNT-F201-018",
        "title": "Radiant Tube Inspection, Decoking & Burners Manual",
        "doc_type": "maintenance_manual",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# MNT-F201-018: Radiant Tube Inspection, Decoking & Burners Manual

## 1.0 RADIANT COIL INSPECTION
Routine inspection checks for radiant coil coking, tube bowing, and wall thickness thinning.
Retire tube section when ultrasonic wall thickness falls below 6.2 mm.

## 2.0 DECOKING PROCEDURE
Execute steam-air decoking cycle when pass differential pressure exceeds 0.35 MPa. Ensure zero-energy verification before mechanical burner maintenance.
""",
    },
    {
        "filename": "doc_demo_trn_gen_019.md",
        "doc_id": "DOC-DEMO-TRN-GEN-019",
        "title": "Fundamentals of Thermal Cracking",
        "doc_type": "training_material",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# TRN-GEN-019: Fundamentals of Thermal Cracking

## 1.0 PYROLYSIS OVERVIEW
Thermal cracking of hydrocarbons involves high-temperature endothermic reactions in tubular coils to produce ethylene and propylene.
Control of residence time and temperature profile is critical.
""",
    },
    {
        "filename": "doc_demo_dat_c101_020.md",
        "doc_id": "DOC-DEMO-DAT-C101-020",
        "title": "Cracked Gas Compressor C-101 Datasheet",
        "doc_type": "equipment_datasheet",
        "equipment_id": "C-101",
        "equipment_type": "compressor",
        "unit_area": "UNIT-CRACK-01",
        "content": """# DAT-C101-020: Cracked Gas Compressor C-101 Datasheet

## 1.0 SPECIFICATIONS
- Equipment ID: C-101
- Equipment Name: Cracked Gas Compressor C-101 (4-Stage Centrifugal)
- Connected Upstream: TLE-201 and Primary Fractionator T-101
- Design Speed: 4850.0 RPM; Suction Pressure: 0.12 MPa; Discharge: 3.45 MPa
""",
    },
    {
        "filename": "doc_demo_eng_hrc_021.md",
        "doc_id": "DOC-DEMO-ENG-HRC-021",
        "title": "Plant Asset Hierarchy & Tag Directory",
        "doc_type": "engineering_document",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# ENG-HRC-021: Plant Asset Hierarchy & Tag Directory

## 1.0 PLANT HIERARCHY
Cracking Unit UNIT-CRACK-01 contains upstream feed pumps P-101A/P-101B and knockout vessel V-201A.
Furnace F-201A feeds effluent downstream to quench exchanger TLE-201, fractionator T-101, and gas compressor C-101.
""",
    },
    {
        "filename": "doc_demo_mnt_his_022.md",
        "doc_id": "DOC-DEMO-MNT-HIS-022",
        "title": "Furnace F-201A Maintenance Log & Work Orders",
        "doc_type": "maintenance_log",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# MNT-HIS-022: Furnace F-201A Maintenance Log & Work Orders

## 1.0 LOG HISTORY
- WO-2026-0814: Thermocouple calibration and drift rectification on Pass 4.
- WO-2026-0512: Scheduled steam-air decoke cycle to remove coking accumulation.
- WO-2025-1102: Pyrometer optical lens cleaning and draft transmitter recalibration.
""",
    },
    {
        "filename": "doc_demo_inc_f201_023.md",
        "doc_id": "DOC-DEMO-INC-F201-023",
        "title": "Incident Retrospective & Lessons Learned: 2025 Thermal Excursion",
        "doc_type": "incident_retrospective",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# INC-F201-023: Incident Retrospective & Lessons Learned: 2025 Thermal Excursion

## 1.0 INCIDENT SUMMARY
During an upset in November 2025, severe coking in Pass 3 caused an unexpected temperature excursion exceeding 890 °C.

## 2.0 ROOT CAUSE AND LESSONS LEARNED
Root cause was identified as fuel gas valve hunting and localized coking. Preventive action: enhanced cross-correlation monitoring of skin temperatures against draft.
""",
    },
    {
        "filename": "doc_demo_inc_nrm_024.md",
        "doc_id": "DOC-DEMO-INC-NRM-024",
        "title": "Near-Miss Incident Log & Preventive Actions",
        "doc_type": "near_miss_log",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# INC-NRM-024: Near-Miss Incident Log & Preventive Actions

## 1.0 NEAR-MISS LOG
Near-miss record NM-2026-03: Transient pressure spike on fuel gas line caused brief burner flame liftoff. Prevented emergency trip through fast operator response.
""",
    },
    {
        "filename": "doc_demo_pmt_sop_025.md",
        "doc_id": "DOC-DEMO-PMT-SOP-025",
        "title": "Permit-to-Work Master Specification",
        "doc_type": "permit_standard",
        "equipment_id": "F-201A",
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "content": """# PMT-SOP-025: Permit-to-Work Master Specification

## 1.0 HOT WORK PERMIT RULES
Executing hot work on or near cracking furnace F-201A requires a formal Hot Work Permit.
Mandatory controls include:
1. Gas test at the work location verifying 0% LEL prior to permit sign-off.
2. Continuous dedicated fire watch on station throughout the operation and for 30 minutes post-work.
3. Verification of positive LOTO energy isolation and spectacle blinds.
""",
    },
]


def generate() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for doc in DOCUMENTS:
        file_path = DEMO_DIR / doc["filename"]
        frontmatter = (
            f"---\n"
            f"document_id: {doc['doc_id']}\n"
            f"title: \"{doc['title']}\"\n"
            f"document_type: {doc['doc_type']}\n"
            f"equipment_id: {doc['equipment_id']}\n"
            f"equipment_type: {doc['equipment_type']}\n"
            f"unit_area: {doc['unit_area']}\n"
            f"source: \"NOVA Synthetic Engineering Knowledge Archive\"\n"
            f"version: \"v1.0.0-demo\"\n"
            f"revision: \"A\"\n"
            f"effective_date: \"2026-01-01\"\n"
            f"authority: \"demo_only\"\n"
            f"---\n\n"
        )
        file_path.write_text(frontmatter + doc["content"].strip() + "\n", encoding="utf-8")
        print(f"Generated: {file_path.name}")
    print(f"Successfully generated {len(DOCUMENTS)} documents in {DEMO_DIR}")


if __name__ == "__main__":
    generate()
