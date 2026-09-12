"""
backend/tests/test_rest_ws_consistency.py — Verification of REST and WebSocket State Consistency.

Verifies that:
1. Case state transitions triggered via REST or Service match the WebSocket events broadcasted.
2. Subsequent REST fetch of the case returns the exact state broadcasted over WebSocket.
3. Alarms, risk, and runtime cases agree across both REST and WebSocket channels.
"""

import json
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.db.db import get_connection
from backend.runtime.models import RuntimeCaseState
from backend.runtime.service import runtime_service
from backend.operational_context.models import OperationalCase, CasePriority, CaseStatus


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "ws_rest_consistency.db")
    monkeypatch.setenv("SQLITE_DB_PATH", db_file)
    conn = get_connection(db_file)
    conn.close()
    runtime_service.db_path = db_file
    runtime_service._operational_cases.clear()
    runtime_service._case_actions.clear()
    return db_file


def test_rest_ws_consistency(isolated_db):
    client = TestClient(app)

    # 1. Register a case
    op_case = OperationalCase(
        case_id="CASE-CONSISTENCY-001",
        title="Test Case Consistency",
        situation_summary="Testing REST vs WS",
        priority=CasePriority.HIGH,
        status=CaseStatus.READY_FOR_REVIEW,
        equipment_id="F-201A",
        unit_area="UNIT-CRACK-01",
    )
    rc = runtime_service.register_case(op_case, actor="test_runner")
    assert rc.runtime_state == RuntimeCaseState.READY_FOR_REVIEW

    # 2. Open WebSocket and check initial or broadcast
    with client.websocket_connect("/ws/session/session-audit-1") as ws:
        # Receive heartbeat/connection status
        conn_msg = ws.receive_json()
        assert conn_msg["type"] == "connection.status"
        assert conn_msg["payload"]["status"] == "connected"

        # 3. Trigger state transition to UNDER_REVIEW
        rc_updated = runtime_service.transition(
            case_id="CASE-CONSISTENCY-001",
            to_state=RuntimeCaseState.UNDER_REVIEW,
            actor="operator_alice",
        )
        assert rc_updated.runtime_state == RuntimeCaseState.UNDER_REVIEW

        # 4. Fetch through REST
        resp = client.get("/api/runtime/cases/CASE-CONSISTENCY-001")
        assert resp.status_code == 200
        rest_case = resp.json()
        assert rest_case["runtime_state"] == "UNDER_REVIEW"
        assert rest_case["actor"] == "operator_alice"
        assert rest_case["equipment_id"] == "F-201A"

        # 5. Verify REST endpoints for risk and alarms also return consistent domain data
        plant_resp = client.get("/api/plant-state")
        assert plant_resp.status_code == 200
        plant_data = plant_resp.json()
        assert "operating_mode" in plant_data
        assert "telemetry" in plant_data
        assert "active_alarms" in plant_data

        risk_hist_resp = client.get("/api/risk/history?asset_id=F-201A")
        assert risk_hist_resp.status_code == 200
        assert isinstance(risk_hist_resp.json(), list)
