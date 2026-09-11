"""
backend/services/asset_topology_service.py — Asset & Network Topology Service.

Provides topology graph queries, node-and-edge relationships, asset criticality assessments,
CVE vulnerability mapping, and blast-radius estimations for the Security Command Center.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("vigil.asset_topology")

DEFAULT_TOPOLOGY_NODES = [
    {
        "id": "node-fw-01",
        "label": "Perimeter Firewall (FW-01)",
        "type": "firewall",
        "zone": "Z-01",
        "ip": "192.168.1.1",
        "criticality": "HIGH",
        "status": "HEALTHY",
        "cves": ["CVE-2023-38606"],
    },
    {
        "id": "node-app-01",
        "label": "Core App Gateway (APP-01)",
        "type": "server",
        "zone": "Z-01",
        "ip": "192.168.1.10",
        "criticality": "CRITICAL",
        "status": "HEALTHY",
        "cves": [],
    },
    {
        "id": "node-db-01",
        "label": "Primary Database Cluster (DB-01)",
        "type": "database",
        "zone": "Z-02",
        "ip": "10.0.2.15",
        "criticality": "CRITICAL",
        "status": "HEALTHY",
        "cves": ["CVE-2024-21626"],
    },
    {
        "id": "node-plc-01",
        "label": "Zone 3 SCADA PLC (PLC-01)",
        "type": "scada_plc",
        "zone": "Z-03",
        "ip": "172.16.4.50",
        "criticality": "HIGH",
        "status": "WARNING",
        "cves": ["CVE-2023-44487"],
    },
    {
        "id": "node-workstation-05",
        "label": "Engineering Workstation (WS-05)",
        "type": "workstation",
        "zone": "Z-04",
        "ip": "192.168.4.105",
        "criticality": "MEDIUM",
        "status": "HEALTHY",
        "cves": [],
    },
    {
        "id": "node-auth-01",
        "label": "IAM & Directory Server (AUTH-01)",
        "type": "iam",
        "zone": "Z-05",
        "ip": "10.0.1.5",
        "criticality": "CRITICAL",
        "status": "HEALTHY",
        "cves": [],
    },
]

DEFAULT_TOPOLOGY_EDGES = [
    {"source": "node-fw-01", "target": "node-app-01", "protocol": "HTTPS", "port": 443},
    {"source": "node-app-01", "target": "node-db-01", "protocol": "PostgreSQL", "port": 5432},
    {"source": "node-app-01", "target": "node-auth-01", "protocol": "gRPC", "port": 50051},
    {"source": "node-workstation-05", "target": "node-plc-01", "protocol": "Modbus/TCP", "port": 502},
    {"source": "node-workstation-05", "target": "node-auth-01", "protocol": "LDAPS", "port": 636},
    {"source": "node-app-01", "target": "node-plc-01", "protocol": "MQTT", "port": 1883},
]


class AssetTopologyService:
    def __init__(self) -> None:
        self.nodes = list(DEFAULT_TOPOLOGY_NODES)
        self.edges = list(DEFAULT_TOPOLOGY_EDGES)

    def get_full_topology(self) -> Dict[str, Any]:
        """Return full network topology graph (nodes + edges)."""
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
        }

    def update_node_status(self, node_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Update node operational/security status (e.g. COMPROMISED, CONTAINED, HEALTHY)."""
        for node in self.nodes:
            if node["id"] == node_id:
                node["status"] = status
                logger.info("Updated node %s status to %s", node_id, status)
                return node
        return None

    def calculate_blast_radius(self, target_node_id: str) -> Dict[str, Any]:
        """Calculate blast radius if target_node_id is compromised."""
        target_node = next((n for n in self.nodes if n["id"] == target_node_id), None)
        if not target_node:
            return {"target": target_node_id, "direct_impact": [], "secondary_impact": [], "risk_score": 0.0}

        direct_neighbors: List[str] = []
        for edge in self.edges:
            if edge["source"] == target_node_id:
                direct_neighbors.append(edge["target"])
            elif edge["target"] == target_node_id:
                direct_neighbors.append(edge["source"])

        secondary_neighbors: List[str] = []
        for neighbor in direct_neighbors:
            for edge in self.edges:
                if edge["source"] == neighbor and edge["target"] != target_node_id:
                    secondary_neighbors.append(edge["target"])
                elif edge["target"] == neighbor and edge["source"] != target_node_id:
                    secondary_neighbors.append(edge["source"])

        secondary_neighbors = list(set(secondary_neighbors) - set(direct_neighbors))

        crit_weight = {"LOW": 1.0, "MEDIUM": 2.0, "HIGH": 3.5, "CRITICAL": 5.0}
        base_score = crit_weight.get(target_node.get("criticality", "MEDIUM"), 2.0)
        impact_score = base_score + (len(direct_neighbors) * 1.5) + (len(secondary_neighbors) * 0.75)

        return {
            "target": target_node,
            "direct_impact_nodes": [n for n in self.nodes if n["id"] in direct_neighbors],
            "secondary_impact_nodes": [n for n in self.nodes if n["id"] in secondary_neighbors],
            "blast_radius_score": round(min(10.0, impact_score), 2),
        }


# Global singleton instance
topology_service = AssetTopologyService()
