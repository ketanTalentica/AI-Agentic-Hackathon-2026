from langgraph_agents.langgraph_system import BaseAgent
from typing import Dict, Any

class RetrievalAgent(BaseAgent):
    """
    AGENT: Knowledge Retrieval Agent (RAG)
    DESCRIPTION: Search large docs (PDF, Word, Images) and return relevant context.
    CAPABILITIES: rag, document_search, image_indexing, retrieval, chunking
    OWNS: [PRD 3.1 & 3.2] All Document Parsing (OCR, PDF), Chunking, and Vector Search logic.
    REQUIRED_PACKAGES: langchain, chromadb, pypdf, python-docx
    """

    async def _execute_impl(self) -> Dict[str, Any]:
        """
        Implementation of RAG retrieval.
        """
        import os
        import json
        from pathlib import Path

        # Lazy imports for heavy libs
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            return {"status": "failed", "error": f"Missing dependency: {e}"}

        # Load retrieval config
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policies", "retrieval_config.json")
            with open(cfg_path, "r", encoding="utf-8") as cf:
                rcfg = json.load(cf)
        except Exception:
            rcfg = {
                "chunking": {"chunk_size": 512, "chunk_overlap": 50},
                "vector_store": {"collection_name": "support_docs_v1"},
                "search": {"default_top_k": 1, "min_relevance_score": 0.0, "max_results_limit": 1},
                "source_weights": {}
            }

        collection_name = rcfg.get("vector_store", {}).get("collection_name", "support_docs_v1")
        top_k = rcfg.get("search", {}).get("default_top_k", 5)
        min_score = rcfg.get("search", {}).get("min_relevance_score", 0.0)
        source_weights = rcfg.get("source_weights", {})

        # Get user query from state store
        user_input = await self.state_store.get("user_input")
        if isinstance(user_input, dict):
            query_text = user_input.get("user_input", "")
        else:
            query_text = str(user_input or "")

        if not query_text:
            return {"status": "failed", "error": "No user input found for retrieval"}

        # Initialize embedding model
        embed_model = SentenceTransformer("all-MiniLM-L6-v2")

        # Initialize chroma client and collection
        client = chromadb.Client()
        try:
            collection = client.get_collection(name=collection_name)
        except Exception:
            collection = client.create_collection(name=collection_name)
            # Try to restore from backup if available
            backup_path = Path(os.path.dirname(os.path.dirname(__file__))) / "chroma_backup.jsonl"
            if backup_path.exists():
                try:
                    ids = []
                    docs = []
                    metas = []
                    embs = []
                    with open(backup_path, "r", encoding="utf-8") as bf:
                        for line in bf:
                            obj = json.loads(line)
                            ids.append(obj.get("id"))
                            docs.append(obj.get("document"))
                            metas.append(obj.get("metadata"))
                    for d in docs:
                        embs.append(embed_model.encode(d).tolist())
                    if ids:
                        collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
                except Exception:
                    pass

        # Create query embedding
        q_emb = embed_model.encode(query_text).tolist()

        # Query the collection
        try:
            raw = collection.query(query_embeddings=[q_emb], n_results=rcfg.get("search", {}).get("max_results_limit", top_k), include=["metadatas", "documents", "distances"])
        except Exception as e:
            return {"status": "failed", "error": f"Chroma query error: {e}"}

        results = []
        docs_list = raw.get("documents", [[]])[0]
        metas_list = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]

        for idx, doc in enumerate(docs_list):
            dist = None
            try:
                dist = dists[idx]
            except Exception:
                dist = None

            score = None
            if dist is None:
                score = 0.0
            else:
                # convert distance to similarity and clamp to [-1.0, 1.0]
                try:
                    sim = 1.0 - float(dist)
                except Exception:
                    sim = 0.0
                if sim != sim:  # NaN
                    sim = 0.0
                if sim > 1.0:
                    sim = 1.0
                if sim < -1.0:
                    sim = -1.0
                score = sim

            meta = metas_list[idx] if idx < len(metas_list) else {}
            source_type = meta.get("source_type") if isinstance(meta, dict) else None
            multiplier = float(source_weights.get(source_type, 1.0))
            final_score = score * multiplier

            results.append({
                "id": meta.get("source_path", f"doc_{idx}"),
                "score": final_score,
                "raw_score": score,
                "metadata": meta,
                "snippet": doc
            })

        # Filter and sort
        filtered = [r for r in results if r.get("raw_score", 0) >= min_score]
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

        # If filtering removed everything, fallback to best available candidates
        if not filtered:
            if self.debug:
                print(f"[RetrievalAgent] No results above min_score={min_score}. Falling back to top {top_k} candidates.")
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            # deduplicate by source path + chunk_index while preserving order
            seen = set()
            deduped = []
            for r in results:
                meta = r.get("metadata") or {}
                key = (meta.get("source_path"), meta.get("chunk_index"))
                if key not in seen:
                    seen.add(key)
                    deduped.append(r)
            top_results = deduped[:top_k]
        else:
            # deduplicate filtered results as well
            seen = set()
            deduped = []
            for r in filtered:
                meta = r.get("metadata") or {}
                key = (meta.get("source_path"), meta.get("chunk_index"))
                if key not in seen:
                    seen.add(key)
                    deduped.append(r)
            top_results = deduped[:top_k]

        # Post-process snippets to extract a single matching Q/A when possible
        import re

        def extract_best_qa(snippet: str, query: str) -> str:
            if not snippet:
                return snippet
            s = snippet.replace('\r', '\n')
            # find Q: blocks
            qa_blocks = re.findall(r"Q:.*?(?=(?:\nQ:)|\Z)", s, flags=re.S)
            if not qa_blocks:
                return s
            qlow = (query or "").lower()
            # prefer block containing the query text
            for b in qa_blocks:
                if qlow and qlow in b.lower():
                    return b.strip()
            # otherwise return the first block
            return qa_blocks[0].strip()

        for r in top_results:
            try:
                r['snippet'] = extract_best_qa(r.get('snippet', ''), query_text)
            except Exception:
                pass

        # Write to state store for other agents
        await self.state_store.set("retrieved_context", top_results)

        return {"status": "retrieval_complete", "results_count": len(top_results)}
