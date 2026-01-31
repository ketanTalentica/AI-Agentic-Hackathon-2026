from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
backup = ROOT / "chroma_backup.jsonl"
if backup.exists():
    try:
        backup.unlink()
        print(f"Removed backup: {backup}")
    except Exception as e:
        print("Failed to remove backup:", e)
else:
    print("No backup file found")

try:
    import chromadb
    client = chromadb.Client()
    try:
        client.delete_collection(name="support_docs_v1")
        print("Deleted collection: support_docs_v1")
    except Exception as e:
        print("Chroma delete_collection error:", e)
except Exception as e:
    print("Chroma client not available:", e)
