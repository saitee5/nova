"""
backend/operational_context/builder.py — Operational Intelligence Case Builder for NOVA.

Assembles telemetry observations, ML assessments across 4 models, alarms, multi-domain
RAG evidence, equipment topology, maintenance logs, safety matrices, permit rules, and
incident retrospectives into a single canonical OperationalCase.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from backend.knowledge.build_demo_corpus import build_demo_knowledge_base
from backend.knowledge.evidence_bridge import ModelEvidenceBridge
from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.models import (
    CanonicalEvidence,
    DocumentType,
    EvidenceType,
    RetrievalStatus,
)
from backend.ml.inference.pipeline import MLPipeline
from backend.models.industrial_domain import MLAssessment
from backend.operational_context.models import (
    CasePriority,
    CaseStatus,
    EquipmentDetailContext,
    MLAssessmentSummary,
    Observation,
    ObservationQuality,
    OperationalCase,
    RiskIndicator,
)

logger = logging.getLogger("nova.operational_context.builder")


# ---------------------------------------------------------------------------
# Plant Asset Metadata & Topology Directory
# ---------------------------------------------------------------------------

KNOWN_EQUIPMENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "F-201A": {
        "equipment_type": "furnace",
        "unit_area": "UNIT-CRACK-01",
        "name": "Cracking Furnace F-201A (Radiant Pyrolysis)",
        "design_limits": {
            "cot_normal_min_deg_c": 840.0,
            "cot_normal_max_deg_c": 860.0,
            "cot_alarm_high_deg_c": 885.0,
            "cot_trip_high_high_deg_c": 895.0,
            "tmt_alarm_high_deg_c": 1040.0,
            "tmt_trip_high_high_deg_c": 1080.0,
            "fuel_gas_pressure_normal_mpa": 0.30,
            "feed_rate_normal_kg_h": 24000.0,
            "draft_normal_pa": -30.0,
        },
        "connected_upstream": ["P-101A", "P-101B", "V-201A"],
        "connected_downstream": ["TLE-201", "T-101", "C-101"],
        "associated_tags": ["TI-201", "TI-201B", "TI-201C", "TI-204", "PI-201", "PI-204", "FV-201", "FC-201", "SV-204"],
        "relevant_datasheets": ["DOC-DEMO-DAT-F201-015", "DOC-DEMO-ENG-HRC-021", "DOC-DEMO-PID-TOP-017"],
    },
    "P-101A": {
        "equipment_type": "pump",
        "unit_area": "UNIT-CRACK-01",
        "name": "Hydrocarbon Feed Pump P-101A (Primary)",
        "design_limits": {
            "suction_pressure_min_mpa": 0.25,
            "discharge_pressure_normal_mpa": 0.55,
            "rated_flow_m3_h": 45.0,
        },
        "connected_upstream": ["TK-101"],
        "connected_downstream": ["F-201A", "V-201A"],
        "associated_tags": ["PI-101", "PI-102", "FI-101", "VI-101"],
        "relevant_datasheets": ["DOC-DEMO-DAT-P101-016"],
    },
    "C-101": {
        "equipment_type": "compressor",
        "unit_area": "UNIT-CRACK-01",
        "name": "Cracked Gas Compressor C-101 (4-Stage Centrifugal)",
        "design_limits": {
            "suction_pressure_mpa": 0.12,
            "discharge_pressure_mpa": 3.45,
            "speed_rpm": 4850.0,
        },
        "connected_upstream": ["TLE-201", "T-101"],
        "connected_downstream": ["DEETHANIZER", "FRACTIONATION"],
        "associated_tags": ["PI-1011", "PI-1014", "TI-1011", "VI-1011", "FV-1011"],
        "relevant_datasheets": ["DOC-DEMO-DAT-C101-020"],
    },
}


class OperationalContextBuilder:
    """
    Core builder class that constructs a structured OperationalCase from
    telemetry, ML inference assessments, alarms, and multi-domain RAG retrieval.
    """

    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        ml_pipeline: Optional[MLPipeline] = None,
    ) -> None:
        self.kb = knowledge_base
        self.ml_pipeline = ml_pipeline

    def _get_kb(self) -> KnowledgeBase:
        if self.kb is None:
            self.kb = build_demo_knowledge_base()
        return self.kb

    def _get_ml_pipeline(self) -> MLPipeline:
        if self.ml_pipeline is None:
            self.ml_pipeline = MLPipeline()
        return self.ml_pipeline

    def build_case(
        self,
        telemetry: Union[List[Observation], Dict[str, float], Dict[str, Any]],
        equipment_id: str = "F-201A",
        equipment_type: Optional[str] = None,
        unit_area: str = "UNIT-CRACK-01",
        alarms: Optional[List[Dict[str, Any]]] = None,
        scenario_context: Optional[str] = None,
        precomputed_assessments: Optional[Dict[str, Any]] = None,
    ) -> OperationalCase:
        """
        Build a comprehensive, fully traced OperationalCase.
        """
        # 1. Normalize Observations
        observations: List[Observation] = []
        raw_telemetry_dict: Dict[str, float] = {}

        if isinstance(telemetry, list):
            for item in telemetry:
                if isinstance(item, Observation):
                    observations.append(item)
                    raw_telemetry_dict[item.tag] = item.value
                elif isinstance(item, dict):
                    obs = Observation(**item)
                    observations.append(obs)
                    raw_telemetry_dict[obs.tag] = obs.value
        elif isinstance(telemetry, dict):
            for k, v in telemetry.items():
                if isinstance(v, (int, float)):
                    raw_telemetry_dict[str(k)] = float(v)
                    observations.append(
                        Observation(
                            tag=str(k),
                            value=float(v),
                            unit=_infer_unit_from_tag(str(k)),
                            source="telemetry",
                            is_synthetic=True,
                            description=f"Process reading for {k}",
                        )
                    )
                elif isinstance(v, dict):
                    obs = Observation(**v)
                    observations.append(obs)
                    raw_telemetry_dict[obs.tag] = obs.value

        # 2. Equipment Context
        equip_info = KNOWN_EQUIPMENT_REGISTRY.get(equipment_id, {})
        resolved_type = equipment_type or equip_info.get("equipment_type", "furnace")
        resolved_unit = equip_info.get("unit_area", unit_area)

        equip_context = EquipmentDetailContext(
            equipment_id=equipment_id,
            equipment_type=resolved_type,
            unit_area=resolved_unit,
            name=equip_info.get("name", f"Asset {equipment_id}"),
            design_limits=equip_info.get("design_limits", {}),
            connected_upstream=equip_info.get("connected_upstream", []),
            connected_downstream=equip_info.get("connected_downstream", []),
            associated_tags=equip_info.get("associated_tags", []),
            relevant_datasheets=equip_info.get("relevant_datasheets", []),
        )

        # 3. Aggregate ML Assessments across 4 Models
        ml_summaries: Dict[str, MLAssessmentSummary] = {}
        ml_evidence_items: List[CanonicalEvidence] = []

        raw_assessments = precomputed_assessments
        if raw_assessments is None:
            try:
                pipeline = self._get_ml_pipeline()
                raw_assessments = pipeline.run_pipeline(raw_telemetry_dict, asset_id=equipment_id)
            except Exception as ex:
                logger.warning("ML Pipeline inference skipped or failed: %s", ex)
                raw_assessments = {}

        ml_summaries = self._aggregate_ml_assessments(raw_assessments or {})
        ml_evidence_items = self._create_ml_evidence(ml_summaries)

        # 4. Multi-Domain RAG Retrieval & Categorization
        kb = self._get_kb()
        rag_results = self._retrieve_and_categorize_evidence(
            kb=kb,
            equipment_id=equipment_id,
            observations=observations,
            ml_summaries=ml_summaries,
            alarms=alarms or [],
            scenario_context=scenario_context,
        )

        # 5. Evaluate Transparent Risk Indicators
        risk_indicators = self._evaluate_risk_indicators(
            observations=observations,
            ml_summaries=ml_summaries,
            alarms=alarms or [],
            rag_results=rag_results,
            equip_context=equip_context,
        )

        # 6. Evaluate Case Priority
        priority = self._determine_case_priority(risk_indicators, alarms or [])

        # 7. Compose Case Summary & Overall State
        overall_state, summary_title, situation_summary = self._synthesize_case_summary(
            equipment_id=equipment_id,
            priority=priority,
            observations=observations,
            ml_summaries=ml_summaries,
            alarms=alarms or [],
            scenario_context=scenario_context,
        )

        # 8. Assemble Provenance and Limitations
        provenance = {
            "builder": "NOVA Operational Intelligence Context Layer",
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "equipment_id": equipment_id,
            "observations_count": len(observations),
            "alarms_count": len(alarms or []),
            "ml_models_evaluated": list(ml_summaries.keys()),
            "rag_chunks_retrieved": sum(len(evs) for evs in rag_results.values()),
        }

        limitations = [
            "ADVISORY INTELLIGENCE ONLY: This operational case provides decision-support evidence; it does not execute automated control commands.",
            "SYNTHETIC SURROGATE NOTICE: Tube temperature predictions are generated by a physics-informed synthetic surrogate and are NOT measured plant telemetry.",
            "DEMO KNOWLEDGE BASE: All retrieved procedures, safety matrices, permits, and incident reports are synthetic demo documents for NOVA testing.",
            "PERMIT STATUS: Permit evidence represents applicable safety specifications, not currently authorized active operational permits.",
        ]

        return OperationalCase(
            equipment_id=equipment_id,
            equipment_type=resolved_type,
            unit_area=resolved_unit,
            status=CaseStatus.READY_FOR_REVIEW,
            priority=priority,
            title=summary_title,
            summary=situation_summary,
            overall_state=overall_state,
            observations=observations,
            alarms=alarms or [],
            ml_assessments=ml_summaries,
            knowledge_evidence=rag_results.get(EvidenceType.DOCUMENT_EVIDENCE, []),
            maintenance_context=rag_results.get(EvidenceType.MAINTENANCE_EVIDENCE, []),
            safety_context=rag_results.get(EvidenceType.SAFETY_EVIDENCE, []),
            permit_context=rag_results.get(EvidenceType.PERMIT_EVIDENCE, []),
            incident_context=rag_results.get(EvidenceType.INCIDENT_EVIDENCE, []),
            equipment_context=equip_context,
            risk_indicators=risk_indicators,
            provenance=provenance,
            limitations=limitations,
            scenario_type="synthetic_demo",
        )

    # -----------------------------------------------------------------------
    # Helper Methods: ML Aggregation
    # -----------------------------------------------------------------------

    def _aggregate_ml_assessments(
        self,
        raw_assessments: Dict[str, Any],
    ) -> Dict[str, MLAssessmentSummary]:
        """Aggregate the 4 model outputs into standardized MLAssessmentSummary objects."""
        summaries: Dict[str, MLAssessmentSummary] = {}

        # 1. Process Anomaly Detector
        anom_raw = raw_assessments.get("anomaly_detection")
        if anom_raw and isinstance(anom_raw, MLAssessment) and anom_raw.status == "OK":
            pred = anom_raw.prediction or {}
            is_anom = bool(pred.get("is_anomaly", False))
            anom_score = float(pred.get("anomaly_score", anom_raw.score or 0.0))
            summaries["ProcessAnomalyDetector"] = MLAssessmentSummary(
                model_name="ProcessAnomalyDetector",
                model_version=anom_raw.model_version or "v1.1.0",
                status="OK",
                is_available=True,
                predicted_value=is_anom,
                score=anom_score,
                industrial_validation=True,
                provenance=anom_raw.provenance,
                summary=f"Anomaly detected={is_anom} (score={anom_score:.4f})",
            )
        else:
            summaries["ProcessAnomalyDetector"] = MLAssessmentSummary(
                model_name="ProcessAnomalyDetector",
                model_version="v1.1.0",
                status=getattr(anom_raw, "status", "MODEL_NOT_AVAILABLE"),
                is_available=False,
                summary="Anomaly detector assessment unavailable",
            )

        # 2. Process Fault Classifier
        fault_raw = raw_assessments.get("fault_diagnosis")
        if fault_raw and isinstance(fault_raw, MLAssessment) and fault_raw.status == "OK":
            pred = fault_raw.prediction or {}
            fault_id = pred.get("predicted_fault")
            fault_name = pred.get("fault_name", f"Fault {fault_id}")
            conf = float(pred.get("confidence", fault_raw.confidence or 0.0))
            summaries["ProcessFaultClassifier"] = MLAssessmentSummary(
                model_name="ProcessFaultClassifier",
                model_version=fault_raw.model_version or "v1.1.0",
                status="OK",
                is_available=True,
                predicted_value=f"IDV({fault_id}): {fault_name}" if fault_id is not None else "Normal",
                confidence=conf,
                industrial_validation=True,
                provenance=fault_raw.provenance,
                summary=f"Predicted fault={fault_id} ({fault_name}) with confidence {conf:.1%}",
            )
        else:
            summaries["ProcessFaultClassifier"] = MLAssessmentSummary(
                model_name="ProcessFaultClassifier",
                model_version="v1.1.0",
                status=getattr(fault_raw, "status", "MODEL_NOT_AVAILABLE"),
                is_available=False,
                summary="Fault diagnosis assessment unavailable",
            )

        # 3. Furnace COT Predictor
        cot_raw = raw_assessments.get("furnace_cot_prediction")
        if cot_raw and isinstance(cot_raw, MLAssessment) and cot_raw.status in ("OK", "SUCCESS"):
            pred = cot_raw.prediction or {}
            pred_cot = float(pred.get("predicted_cot", cot_raw.score or 0.0))
            conf = float(cot_raw.confidence) if cot_raw.confidence is not None else None
            summaries["FurnaceCOTPredictor"] = MLAssessmentSummary(
                model_name="FurnaceCOTPredictor",
                model_version=cot_raw.model_version or "v1.1.0",
                status="OK",
                is_available=True,
                predicted_value=pred_cot,
                confidence=conf,
                score=pred_cot,
                industrial_validation=True,
                provenance=cot_raw.provenance,
                summary=f"Predicted COT={pred_cot:.1f} °C",
            )
        else:
            summaries["FurnaceCOTPredictor"] = MLAssessmentSummary(
                model_name="FurnaceCOTPredictor",
                model_version="v1.1.0",
                status=getattr(cot_raw, "status", "MODEL_NOT_AVAILABLE"),
                is_available=False,
                summary="Furnace COT predictor assessment unavailable",
            )

        # 4. Tube Temperature Predictor (Synthetic Surrogate)
        tube_raw = raw_assessments.get("tube_temperature_soft_sensor")
        if tube_raw and isinstance(tube_raw, MLAssessment) and tube_raw.status in ("OK", "SUCCESS"):
            pred = tube_raw.prediction or {}
            pred_tmt = float(pred.get("predicted_tmt", tube_raw.score or 0.0))
            conf = float(tube_raw.confidence) if tube_raw.confidence is not None else None
            summaries["TubeTemperaturePredictor"] = MLAssessmentSummary(
                model_name="TubeTemperaturePredictor",
                model_version=tube_raw.model_version or "v1.0.0-demo",
                status="OK",
                is_available=True,
                predicted_value=pred_tmt,
                confidence=conf,
                score=pred_tmt,
                target_type="physics_informed_synthetic_surrogate",
                industrial_validation=False,
                provenance={
                    **tube_raw.provenance,
                    "target_type": "physics_informed_synthetic_surrogate",
                    "industrial_validation": False,
                },
                summary=f"Predicted TMT surrogate={pred_tmt:.1f} °C (Synthetic surrogate - Not measured telemetry)",
            )
        else:
            summaries["TubeTemperaturePredictor"] = MLAssessmentSummary(
                model_name="TubeTemperaturePredictor",
                model_version="v1.0.0-demo",
                status=getattr(tube_raw, "status", "MODEL_NOT_AVAILABLE"),
                is_available=False,
                target_type="physics_informed_synthetic_surrogate",
                industrial_validation=False,
                summary="Tube temperature surrogate assessment unavailable",
            )

        return summaries

    def _create_ml_evidence(
        self,
        ml_summaries: Dict[str, MLAssessmentSummary],
    ) -> List[CanonicalEvidence]:
        """Convert MLAssessmentSummaries into CanonicalEvidence with MODEL_EVIDENCE type."""
        evidence_list: List[CanonicalEvidence] = []
        for name, summary in ml_summaries.items():
            if not summary.is_available or summary.status != "OK":
                continue
            if name == "ProcessAnomalyDetector":
                ev = ModelEvidenceBridge.from_anomaly_prediction(
                    {"is_anomaly": summary.predicted_value, "anomaly_score": summary.score or 0.0},
                    model_version=summary.model_version,
                )
                evidence_list.append(ev)
            elif name == "ProcessFaultClassifier":
                ev = ModelEvidenceBridge.from_fault_prediction(
                    {"predicted_fault": summary.predicted_value, "confidence": summary.confidence or 0.0},
                    model_version=summary.model_version,
                )
                evidence_list.append(ev)
            elif name == "FurnaceCOTPredictor":
                ev = ModelEvidenceBridge.from_cot_prediction(
                    {"predicted_cot": summary.predicted_value, "confidence": summary.confidence or 0.0},
                    model_version=summary.model_version,
                )
                evidence_list.append(ev)
            elif name == "TubeTemperaturePredictor":
                ev = ModelEvidenceBridge.from_tube_temp_prediction(
                    {"predicted_tmt": summary.predicted_value, "confidence": summary.confidence or 0.0},
                    model_version=summary.model_version,
                )
                evidence_list.append(ev)
        return evidence_list

    # -----------------------------------------------------------------------
    # Helper Methods: RAG Retrieval & Categorization
    # -----------------------------------------------------------------------

    def _retrieve_and_categorize_evidence(
        self,
        kb: KnowledgeBase,
        equipment_id: str,
        observations: List[Observation],
        ml_summaries: Dict[str, MLAssessmentSummary],
        alarms: List[Dict[str, Any]],
        scenario_context: Optional[str],
    ) -> Dict[EvidenceType, List[CanonicalEvidence]]:
        """Retrieve multi-domain evidence from the KnowledgeBase and distribute across categories."""
        categorized: Dict[EvidenceType, List[CanonicalEvidence]] = {
            EvidenceType.DOCUMENT_EVIDENCE: [],
            EvidenceType.MAINTENANCE_EVIDENCE: [],
            EvidenceType.SAFETY_EVIDENCE: [],
            EvidenceType.PERMIT_EVIDENCE: [],
            EvidenceType.INCIDENT_EVIDENCE: [],
            EvidenceType.EQUIPMENT_EVIDENCE: [],
        }

        # Build dynamic queries based on operational cues
        query_terms: List[str] = [equipment_id]

        # Check for abnormal observations
        cot_obs = next((o for o in observations if "TI-201" in o.tag or "COT" in o.tag), None)
        if cot_obs and cot_obs.value > 880.0:
            query_terms.append(f"high COT {cot_obs.value:.1f} alarm fuel gas reduction")

        # Check for fault predictions
        fault_sum = ml_summaries.get("ProcessFaultClassifier")
        if fault_sum and fault_sum.is_available and fault_sum.predicted_value:
            query_terms.append(f"fault {fault_sum.predicted_value}")

        # Check for alarms
        for alarm in alarms:
            msg = alarm.get("message", "") or alarm.get("parameter", "")
            if msg:
                query_terms.append(msg)

        if scenario_context:
            query_terms.append(scenario_context)

        combined_query = " ".join(query_terms)

        # 1. Primary Targeted Retrieval
        primary_res = kb.retrieve(query=combined_query, top_k=8)
        if primary_res.status == RetrievalStatus.OK:
            for chunk in primary_res.results:
                ev_type = ModelEvidenceBridge.infer_evidence_type(chunk)
                ev = ModelEvidenceBridge.from_retrieved_chunk(chunk, override_type=ev_type)
                if ev_type in categorized and not any(e.source_id == ev.source_id and e.provenance.get("chunk_id") == ev.provenance.get("chunk_id") for e in categorized[ev_type]):
                    categorized[ev_type].append(ev)

        # 2. Domain-Specific Supplementary Queries to ensure all relevant domains are covered
        # A. Safety Context
        safety_query = f"{equipment_id} safety standard PPE isolation lockout tagout zero-energy Level 3 face shield SAF"
        safety_res = kb.retrieve(query=safety_query, top_k=8)
        if safety_res.status == RetrievalStatus.OK:
            for chunk in safety_res.results:
                ev_type = ModelEvidenceBridge.infer_evidence_type(chunk)
                ev = ModelEvidenceBridge.from_retrieved_chunk(chunk, override_type=ev_type)
                if ev_type in categorized and not any(e.source_id == ev.source_id and e.provenance.get("chunk_id") == ev.provenance.get("chunk_id") for e in categorized[ev_type]):
                    categorized[ev_type].append(ev)

        # B. Permit Context
        permit_query = f"{equipment_id} hot work permit Class A combustible gas test authorized PTW PMT"
        permit_res = kb.retrieve(query=permit_query, top_k=6)
        if permit_res.status == RetrievalStatus.OK:
            for chunk in permit_res.results:
                ev_type = ModelEvidenceBridge.infer_evidence_type(chunk)
                ev = ModelEvidenceBridge.from_retrieved_chunk(chunk, override_type=ev_type)
                if ev_type in categorized and not any(e.source_id == ev.source_id and e.provenance.get("chunk_id") == ev.provenance.get("chunk_id") for e in categorized[ev_type]):
                    categorized[ev_type].append(ev)

        # C. Maintenance Context
        mnt_query = f"{equipment_id} maintenance work order inspection preventative coil decoking pyrometer calibration MNT"
        mnt_res = kb.retrieve(query=mnt_query, top_k=8)
        if mnt_res.status == RetrievalStatus.OK:
            for chunk in mnt_res.results:
                ev_type = ModelEvidenceBridge.infer_evidence_type(chunk)
                ev = ModelEvidenceBridge.from_retrieved_chunk(chunk, override_type=ev_type)
                if ev_type in categorized and not any(e.source_id == ev.source_id and e.provenance.get("chunk_id") == ev.provenance.get("chunk_id") for e in categorized[ev_type]):
                    categorized[ev_type].append(ev)

        # D. Incident Context
        inc_query = f"{equipment_id} incident near-miss retrospective root cause excursion INC"
        inc_res = kb.retrieve(query=inc_query, top_k=8)
        if inc_res.status == RetrievalStatus.OK:
            for chunk in inc_res.results:
                ev_type = ModelEvidenceBridge.infer_evidence_type(chunk)
                ev = ModelEvidenceBridge.from_retrieved_chunk(chunk, override_type=ev_type)
                if ev_type in categorized and not any(e.source_id == ev.source_id and e.provenance.get("chunk_id") == ev.provenance.get("chunk_id") for e in categorized[ev_type]):
                    categorized[ev_type].append(ev)

        return categorized

    # -----------------------------------------------------------------------
    # Helper Methods: Risk Indicators & Priority Evaluation
    # -----------------------------------------------------------------------

    def _evaluate_risk_indicators(
        self,
        observations: List[Observation],
        ml_summaries: Dict[str, MLAssessmentSummary],
        alarms: List[Dict[str, Any]],
        rag_results: Dict[EvidenceType, List[CanonicalEvidence]],
        equip_context: EquipmentDetailContext,
    ) -> List[RiskIndicator]:
        """Evaluate explicit, traceable risk indicators."""
        indicators: List[RiskIndicator] = []

        # 1. Anomaly Detector
        anom_sum = ml_summaries.get("ProcessAnomalyDetector")
        if anom_sum and anom_sum.is_available:
            is_anom = bool(anom_sum.predicted_value)
            score = anom_sum.score or 0.0
            indicators.append(
                RiskIndicator(
                    name="anomaly_detected",
                    value=is_anom,
                    source="ProcessAnomalyDetector v1.1.0",
                    severity=CasePriority.HIGH if (is_anom and score > 0.80) else (CasePriority.MEDIUM if is_anom else CasePriority.INFO),
                    description=f"Process anomaly state is {is_anom} with anomaly score {score:.4f}.",
                    provenance=anom_sum.provenance,
                )
            )

        # 2. Fault Classifier
        fault_sum = ml_summaries.get("ProcessFaultClassifier")
        if fault_sum and fault_sum.is_available and fault_sum.predicted_value and fault_sum.predicted_value != "Normal":
            conf = fault_sum.confidence or 0.0
            indicators.append(
                RiskIndicator(
                    name="fault_classified",
                    value=fault_sum.predicted_value,
                    source="ProcessFaultClassifier v1.1.0",
                    severity=CasePriority.HIGH if conf >= 0.70 else CasePriority.MEDIUM,
                    description=f"Diagnosed fault {fault_sum.predicted_value} with classification confidence {conf:.1%}.",
                    provenance=fault_sum.provenance,
                )
            )

        # 3. COT Thresholds
        cot_obs = next((o for o in observations if "TI-201" in o.tag or "COT" in o.tag), None)
        if cot_obs:
            limits = equip_context.design_limits
            alarm_high = limits.get("cot_alarm_high_deg_c", 885.0)
            trip_high = limits.get("cot_trip_high_high_deg_c", 895.0)

            if cot_obs.value >= trip_high:
                indicators.append(
                    RiskIndicator(
                        name="COT_above_emergency_trip",
                        value=cot_obs.value,
                        source=f"Telemetry {cot_obs.tag}",
                        severity=CasePriority.CRITICAL,
                        description=f"Measured COT {cot_obs.value:.1f} °C exceeds emergency high-high limit ({trip_high:.1f} °C).",
                        provenance={"tag": cot_obs.tag, "limit": trip_high},
                    )
                )
            elif cot_obs.value >= alarm_high:
                indicators.append(
                    RiskIndicator(
                        name="COT_above_alarm_threshold",
                        value=cot_obs.value,
                        source=f"Telemetry {cot_obs.tag}",
                        severity=CasePriority.HIGH,
                        description=f"Measured COT {cot_obs.value:.1f} °C exceeds high alarm limit ({alarm_high:.1f} °C).",
                        provenance={"tag": cot_obs.tag, "limit": alarm_high},
                    )
                )

        # 4. TMT Surrogate Elevation
        tube_sum = ml_summaries.get("TubeTemperaturePredictor")
        if tube_sum and tube_sum.is_available and tube_sum.predicted_value:
            tmt_val = float(tube_sum.predicted_value)
            tmt_alarm = equip_context.design_limits.get("tmt_alarm_high_deg_c", 1040.0)
            tmt_trip = equip_context.design_limits.get("tmt_trip_high_high_deg_c", 1080.0)

            if tmt_val >= tmt_trip:
                indicators.append(
                    RiskIndicator(
                        name="TMT_estimate_critical",
                        value=tmt_val,
                        source="TubeTemperaturePredictor v1.0.0-demo",
                        severity=CasePriority.CRITICAL,
                        description=f"Estimated TMT surrogate {tmt_val:.1f} °C exceeds metallurgical trip limit ({tmt_trip:.1f} °C).",
                        provenance=tube_sum.provenance,
                    )
                )
            elif tmt_val >= tmt_alarm:
                indicators.append(
                    RiskIndicator(
                        name="TMT_estimate_elevated",
                        value=tmt_val,
                        source="TubeTemperaturePredictor v1.0.0-demo",
                        severity=CasePriority.HIGH,
                        description=f"Estimated TMT surrogate {tmt_val:.1f} °C exceeds high operating limit ({tmt_alarm:.1f} °C).",
                        provenance=tube_sum.provenance,
                    )
                )

        # 5. Active Alarms
        if alarms:
            indicators.append(
                RiskIndicator(
                    name="active_alarms_present",
                    value=len(alarms),
                    source="DCS Alarm Annunciator",
                    severity=CasePriority.HIGH if any(a.get("severity") in ("HIGH", "CRITICAL") for a in alarms) else CasePriority.MEDIUM,
                    description=f"{len(alarms)} active alarm(s) annunciated on {equip_context.equipment_id}.",
                    provenance={"alarms": [a.get("alarm_id", "ALM") for a in alarms]},
                )
            )

        # 6. Maintenance Context Present
        if rag_results.get(EvidenceType.MAINTENANCE_EVIDENCE):
            indicators.append(
                RiskIndicator(
                    name="maintenance_intervention_active",
                    value=True,
                    source="DOC-DEMO-MNT-HIS-022",
                    severity=CasePriority.MEDIUM,
                    description="Active maintenance work order, inspection, or decoking procedure applicable.",
                    provenance={"domain": "maintenance"},
                )
            )

        # 7. Safety Hazard / Permit Context Present
        if rag_results.get(EvidenceType.SAFETY_EVIDENCE) or rag_results.get(EvidenceType.PERMIT_EVIDENCE):
            indicators.append(
                RiskIndicator(
                    name="safety_and_permit_controls_applicable",
                    value=True,
                    source="DOC-DEMO-SAF-GEN-012",
                    severity=CasePriority.MEDIUM,
                    description="Work requires formal Permit-to-Work, LOTO energy isolation, or PPE high-heat controls.",
                    provenance={"domain": "safety_and_permits"},
                )
            )

        # 8. Incident History Match
        if rag_results.get(EvidenceType.INCIDENT_EVIDENCE):
            indicators.append(
                RiskIndicator(
                    name="historical_incident_match",
                    value=True,
                    source="DOC-DEMO-INC-F201-023",
                    severity=CasePriority.LOW,
                    description="Matching historical incident or near-miss retrospective available for operational context.",
                    provenance={"domain": "incident_retrospective"},
                )
            )

        return indicators

    def _determine_case_priority(
        self,
        risk_indicators: List[RiskIndicator],
        alarms: List[Dict[str, Any]],
    ) -> CasePriority:
        """
        Evaluate deterministic case priority based on explicit indicator rules.
        """
        severities = [ind.severity for ind in risk_indicators]

        # Any CRITICAL indicator -> Case priority is CRITICAL
        if CasePriority.CRITICAL in severities:
            return CasePriority.CRITICAL

        # Any HIGH indicator -> Case priority is HIGH
        if CasePriority.HIGH in severities:
            return CasePriority.HIGH

        # Any MEDIUM indicator -> Case priority is MEDIUM
        if CasePriority.MEDIUM in severities:
            return CasePriority.MEDIUM

        # Any LOW indicator -> Case priority is LOW
        if CasePriority.LOW in severities:
            return CasePriority.LOW

        return CasePriority.INFO

    def _synthesize_case_summary(
        self,
        equipment_id: str,
        priority: CasePriority,
        observations: List[Observation],
        ml_summaries: Dict[str, MLAssessmentSummary],
        alarms: List[Dict[str, Any]],
        scenario_context: Optional[str],
    ) -> tuple[str, str, str]:
        """Synthesize overall_state, title, and summary description."""
        if priority == CasePriority.CRITICAL:
            overall_state = "CRITICAL_EXCURSION"
            title = f"CRITICAL Operational Excursion on {equipment_id}"
            summary = f"Severe thermal or safety limits exceeded on {equipment_id}. Immediate operator mitigation and safety isolation required."
        elif priority == CasePriority.HIGH:
            overall_state = "ABNORMAL_DEVIATION"
            title = f"High Priority Process Deviation on {equipment_id}"
            summary = f"Elevated process temperatures or confirmed process fault on {equipment_id}. Corrective firing adjustments and alarm response required."
        elif priority == CasePriority.MEDIUM:
            overall_state = "DEVIATION_ASSESSING"
            title = f"Moderate Process Upset / Maintenance Alert on {equipment_id}"
            summary = f"Process anomaly or operational intervention identified on {equipment_id}. Applicable SOPs, maintenance records, and permit rules assembled."
        elif priority == CasePriority.LOW:
            overall_state = "ROUTINE_MONITORING"
            title = f"Routine Monitoring / Minor Alert on {equipment_id}"
            summary = f"Operational parameters on {equipment_id} are largely within baseline with minor advisory notes."
        else:
            overall_state = "STEADY_STATE"
            title = f"Normal Steady-State Operation on {equipment_id}"
            summary = f"All process observations and model assessments on {equipment_id} indicate normal operation."

        if scenario_context:
            summary += f" [Context: {scenario_context}]"

        return overall_state, title, summary


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def _infer_unit_from_tag(tag: str) -> str:
    """Infer physical engineering units from standard instrument tag prefixes."""
    u = tag.upper()
    if u.startswith("TI") or "COT" in u or "TMT" in u or "TEMP" in u:
        return "°C"
    if u.startswith("PI") or "PRESS" in u:
        return "MPa"
    if u.startswith("FI") or "FLOW" in u or "FEED" in u:
        return "kg/h"
    if u.startswith("VI") or "VIB" in u:
        return "mm/s"
    if "LEL" in u or "GAS" in u:
        return "% LEL"
    return ""


def build_operational_case(
    telemetry: Union[List[Observation], Dict[str, float], Dict[str, Any]],
    equipment_id: str = "F-201A",
    equipment_type: Optional[str] = None,
    unit_area: str = "UNIT-CRACK-01",
    alarms: Optional[List[Dict[str, Any]]] = None,
    scenario_context: Optional[str] = None,
    kb: Optional[KnowledgeBase] = None,
    ml_pipeline: Optional[MLPipeline] = None,
    precomputed_assessments: Optional[Dict[str, Any]] = None,
) -> OperationalCase:
    """
    Convenience functional API for building an OperationalCase.
    """
    builder = OperationalContextBuilder(knowledge_base=kb, ml_pipeline=ml_pipeline)
    return builder.build_case(
        telemetry=telemetry,
        equipment_id=equipment_id,
        equipment_type=equipment_type,
        unit_area=unit_area,
        alarms=alarms,
        scenario_context=scenario_context,
        precomputed_assessments=precomputed_assessments,
    )
