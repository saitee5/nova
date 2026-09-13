import os
from dotenv import load_dotenv
load_dotenv(".env")

from backend.memory.client import QdrantMemoryClient
from backend.memory.hybrid_search import hybrid_search

client = QdrantMemoryClient()
print("Qdrant health check:", client.health_check())

# 1. Search safety procedures
query = "hot work permit methane leak protocol"
results = hybrid_search(client, "safety_procedures", query, top_k=3)
print(f"\n--- Safety Procedures Query: '{query}' ---")
print(f"Returned {len(results)} hits:")
for r in results:
    print(f"  Record ID: {r['record_id']} | Score: {r['similarity_score']:.4f} | Title: {r.get('title') or r['payload'].get('title')}")
    text_snip = r['payload'].get('text_summary') or r['payload'].get('description') or r['title']
    print(f"  Text snippet: {str(text_snip)[:140]}...")

# 2. Search equipment context
query = "compressor C-14 vibration threshold"
results = hybrid_search(client, "equipment_context", query, top_k=3)
print(f"\n--- Equipment Context Query: '{query}' ---")
print(f"Returned {len(results)} hits:")
for r in results:
    print(f"  Record ID: {r['record_id']} | Score: {r['similarity_score']:.4f} | Title: {r.get('title') or r['payload'].get('title')}")
    text_snip = r['payload'].get('text_summary') or r['payload'].get('description') or r['title']
    print(f"  Text snippet: {str(text_snip)[:140]}...")

# 3. Search historical incidents
query = "furnace radiant coil hotspot burner flame impingement"
results = hybrid_search(client, "incidents_historical", query, top_k=3)
print(f"\n--- Historical Incidents Query: '{query}' ---")
print(f"Returned {len(results)} hits:")
for r in results:
    print(f"  Record ID: {r['record_id']} | Score: {r['similarity_score']:.4f} | Title: {r.get('title') or r['payload'].get('title')}")
    text_snip = r['payload'].get('text_summary') or r['payload'].get('description') or r['title']
    print(f"  Text snippet: {str(text_snip)[:140]}...")
