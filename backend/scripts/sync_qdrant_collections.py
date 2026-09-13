import os
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from dotenv import load_dotenv

load_dotenv(".env")

qdrant_url = os.environ.get("QDRANT_URL")
qdrant_api_key = os.environ.get("QDRANT_API_KEY")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=15.0)

pairs = [
    ("equipment_context", "vigil_equipment_context"),
    ("safety_procedures", "vigil_safety_procedures"),
    ("maintenance_history", "vigil_maintenance_history"),
    ("near_misses", "vigil_near_misses"),
    ("risk_patterns", "vigil_risk_patterns"),
    ("active_case_memory", "vigil_active_case_memory"),
]

for src, dst in pairs:
    src_info = client.get_collection(src)
    dst_info = client.get_collection(dst)
    print(f"{src} ({src_info.points_count}) -> {dst} ({dst_info.points_count})")
    if src_info.points_count > 0 and dst_info.points_count == 0:
        print(f"Syncing points from {src} to {dst}...")
        points, _ = client.scroll(collection_name=src, limit=100, with_payload=True, with_vectors=True)
        print(f"  Fetched {len(points)} points from {src}")
        point_structs = [
            PointStruct(id=p.id, vector=p.vector, payload=p.payload)
            for p in points
        ]
        client.upsert(collection_name=dst, points=point_structs)
        print(f"  Upserted into {dst}! New count: {client.get_collection(dst).points_count}")
