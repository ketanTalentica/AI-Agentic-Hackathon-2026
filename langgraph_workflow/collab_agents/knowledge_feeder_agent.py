from langgraph_agents.langgraph_system import BaseAgent
from typing import Dict, Any, List
import os
import json
import uuid
from pathlib import Path
from datetime import datetime


class KnowledgeFeederAgent(BaseAgent):
    """
    AGENT: Knowledge Feeder
    DESCRIPTION: Accepts file paths from state keys (`knowledge_files` or `ingest_files`),
    extracts text from supported formats, chunks content, embeds with SentenceTransformers
    and indexes into a Chroma collection. Writes a JSONL backup at `chroma_backup.jsonl`.
    """

    async def _execute_impl(self) -> Dict[str, Any]:
        import traceback
        try:
            try:
                import chromadb
                from sentence_transformers import SentenceTransformer
            except Exception as e:
                return {"status": "failed", "error": f"Missing dependency: {e}"}

            root_dir = Path(os.path.dirname(os.path.dirname(__file__)))
            cfg_path = root_dir / "policies" / "retrieval_config.json"
            try:
                with open(cfg_path, "r", encoding="utf-8") as cf:
                    rcfg = json.load(cf)
            except Exception:
                rcfg = {
                    "chunking": {"chunk_size": 512, "chunk_overlap": 50},
                    "vector_store": {"collection_name": "support_docs_v1"},
                    "search": {"default_top_k": 5, "min_relevance_score": 0.0, "max_results_limit": 20},
                    "source_weights": {}
                }

            chunk_size = rcfg.get("chunking", {}).get("chunk_size", 512)
            chunk_overlap = rcfg.get("chunking", {}).get("chunk_overlap", 50)
            collection_name = rcfg.get("vector_store", {}).get("collection_name", "support_docs_v1")

            files_key = await self.state_store.get("knowledge_files")
            if files_key is None:
                files_key = await self.state_store.get("ingest_files")
            if files_key is None:
                files_key = await self.state_store.get("user_input")

            files: List[str] = []
            if isinstance(files_key, str):
                files = [files_key]
            elif isinstance(files_key, (list, tuple)):
                files = list(files_key)
            elif isinstance(files_key, dict):
                files = files_key.get("paths") or files_key.get("files") or []

            if not files:
                return {"status": "failed", "error": "No files provided in 'knowledge_files'/'ingest_files'/'user_input'"}

            embed_model = SentenceTransformer("all-MiniLM-L6-v2")

            all_ids = []
            all_docs = []
            all_metas = []

            def extract_text_from_pdf(path: str) -> str:
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(path)
                    return "\n".join([(p.extract_text() or "") for p in reader.pages])
                except Exception:
                    return ""

            def extract_text_from_docx(path: str) -> str:
                try:
                    from docx import Document
                    doc = Document(path)
                    return "\n".join([p.text for p in doc.paragraphs])
                except Exception:
                    return ""
            def chunk_text(text: str, size: int, overlap: int) -> List[str]:
                if not text:
                    return []
                step = max(size - overlap, 1)
                chunks = []
                start = 0
                text_len = len(text)
                while start < text_len:
                    end = min(start + size, text_len)
                    chunk = text[start:end]
                    chunks.append(chunk.strip())
                    start += step
                return chunks

            for fpath in files:
                try:
                    p = Path(fpath)
                    if not p.exists():
                        p = root_dir / fpath
                    if not p.exists():
                        continue

                    ext = p.suffix.lower()
                    if ext in [".txt", ".md"]:
                        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                            text = fh.read()
                        source_type = "text"
                    elif ext == ".pdf":
                        text = extract_text_from_pdf(str(p))
                        source_type = "pdf"
                    elif ext in [".docx"]:
                        text = extract_text_from_docx(str(p))
                        source_type = "docx"
                    else:
                        text = ""
                        source_type = "unknown"

                    chunks = chunk_text(text, chunk_size, chunk_overlap)
                    for idx, c in enumerate(chunks):
                        cid = f"{p.name}::{idx}::{uuid.uuid4()}"
                        meta = {
                            "source_path": str(p),
                            "source_name": p.name,
                            "source_type": source_type,
                            "chunk_index": idx,
                            "ingestion_timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                        all_ids.append(cid)
                        all_docs.append(c)
                        all_metas.append(meta)
                except Exception:
                    if self.debug:
                        print("[KnowledgeFeederAgent] Failed to process:", fpath, traceback.format_exc())

            if not all_docs:
                return {"status": "failed", "error": "No extractable text found in provided files"}

            try:
                embs = embed_model.encode(all_docs).tolist()
            except Exception:
                embs = [embed_model.encode(d).tolist() for d in all_docs]

            client = chromadb.Client()
            try:
                collection = client.get_collection(name=collection_name)
            except Exception:
                collection = client.create_collection(name=collection_name)

            try:
                collection.add(ids=all_ids, documents=all_docs, metadatas=all_metas, embeddings=embs)
            except Exception as e:
                if self.debug:
                    print("[KnowledgeFeederAgent] Chroma add error:", e)

            backup_path = root_dir / "chroma_backup.jsonl"
            try:
                with open(backup_path, "a", encoding="utf-8") as bf:
                    for i in range(len(all_ids)):
                        line = {"id": all_ids[i], "document": all_docs[i], "metadata": all_metas[i]}
                        bf.write(json.dumps(line, ensure_ascii=False) + "\n")
            except Exception:
                if self.debug:
                    print("[KnowledgeFeederAgent] Failed to write backup")

            result = {"status": "ingested", "count": len(all_docs), "collection": collection_name}
            await self.state_store.set("knowledge_ingestion_result", result)
            return result

        except Exception as e:
            return {"status": "failed", "error": str(e)}
