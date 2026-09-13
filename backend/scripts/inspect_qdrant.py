import os
import json
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv(".env")

qdrant_url = os.environ.get("QDRANT_URL")
qdrant_api_key = os.environ.get("QDRANT_API_KEY")

print(f"Connecting to Qdrant: {qdrant_url}")
client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=10.0)

collections_res = client.get_collections()
print(f"Found {len(collections_res.collections)} collections:")

total_points = 0
coll_info = {}
for c in collections_res.collections:
    info = client.get_collection(c.name)
    count = info.points_count
    total_points += count
    vectors_cfg = info.config.params.vectors
    dim = getattr(vectors_cfg, "size", None)
    dist = getattr(vectors_cfg, "distance", None)
    coll_info[c.name] = {
        "points_count": count,
        "vector_size": dim,
        "distance": str(dist),
    }
    print(f"  {c.name:35}: {count:4} points, dim={dim}, distance={dist}")

print(f"\nTOTAL VECTOR POINTS ACROSS ALL COLLECTIONS: {total_points}")

# Run a real search in one of the collections with documents
target_coll = None
for name, d in coll_info.items():
    if d["points_count"] > 0:
        target_coll = name
        break

if target_coll:
    print(f"\n--- Real Retrieval Query on {target_coll} ---")
    # Sample point to see payload schema
    sample_pts = client.scroll(collection_name=target_coll, limit=2, with_payload=True, with_vectors=False)[0]
    for pt in sample_pts:
        print(f"Sample Point ID: {pt.id}")
        print(f"Payload: {json.dumps(pt.payload, indent=2)}")
