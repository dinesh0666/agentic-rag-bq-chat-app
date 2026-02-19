"""
Schema Vector Store — Real RAG for BigQuery schemas and business rules.

Embeds table schemas, column descriptions, and business rules into an 
in-memory vector store using sentence-transformers + cosine similarity.
Retrieved chunks are injected into LLM prompts as relevant context.
"""

import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer


class SchemaVectorStore:
    """
    In-memory vector store for BigQuery schema chunks and business rules.
    
    Documents are split at column / rule granularity so retrieval returns 
    only the schema sections that are relevant to the user's query.
    """

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        print(f"[RAG] Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        self.documents: List[str] = []      # raw text chunks
        self.metadata: List[Dict] = []       # {type, table, column, ...}
        self.embeddings: Optional[np.ndarray] = None
        self._indexed = False

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_schemas(self, schemas: List[Dict[str, Any]]) -> None:
        """
        Embed BigQuery table schemas into the vector store.
        
        Args:
            schemas: List of schema dicts from BigQueryConnector.get_all_schemas()
        """
        new_docs = []
        new_meta = []

        for schema in schemas:
            table = schema["table_name"]
            desc = schema.get("description", "")

            # Document 1: whole-table summary
            table_doc = f"Table: {table}\n"
            if desc:
                table_doc += f"Description: {desc}\n"
            table_doc += "Columns: " + ", ".join(
                c["name"] for c in schema.get("columns", [])
            )
            new_docs.append(table_doc)
            new_meta.append({"type": "table_summary", "table": table})

            # Document 2+: one chunk per column
            for col in schema.get("columns", []):
                col_doc = (
                    f"Table: {table} | Column: {col['name']} | "
                    f"Type: {col['type']}"
                )
                if col.get("description"):
                    col_doc += f" | Description: {col['description']}"
                new_docs.append(col_doc)
                new_meta.append({
                    "type": "column",
                    "table": table,
                    "column": col["name"],
                    "col_type": col["type"],
                })

        self._add(new_docs, new_meta)
        print(f"[RAG] Indexed {len(new_docs)} schema chunks from {len(schemas)} tables")

    def index_business_rules(self, calculations: List[Any], domain_info: str = "") -> None:
        """
        Embed business calculations and domain context.
        
        Args:
            calculations: List of calculation objects from config_manager
            domain_info: Free-text domain description string
        """
        new_docs = []
        new_meta = []

        for calc in calculations:
            doc = f"Business Calculation: {calc.name}\n"
            if calc.description:
                doc += f"Description: {calc.description}\n"
            if calc.formula:
                doc += f"Formula: {calc.formula}\n"
            if hasattr(calc, "parameters") and calc.parameters:
                doc += "Parameters: " + ", ".join(
                    f"{p}" for p in calc.parameters
                )
            new_docs.append(doc)
            new_meta.append({"type": "calculation", "name": calc.name})

        if domain_info:
            new_docs.append(f"Domain Context:\n{domain_info}")
            new_meta.append({"type": "domain"})

        if new_docs:
            self._add(new_docs, new_meta)
            print(f"[RAG] Indexed {len(new_docs)} business rule chunks")

    def _add(self, docs: List[str], meta: List[Dict]) -> None:
        """Add documents and recompute embeddings."""
        self.documents.extend(docs)
        self.metadata.extend(meta)
        print(f"[RAG] Embedding {len(docs)} new chunks...")
        new_embeddings = self.model.encode(docs, normalize_embeddings=True)
        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])
        self._indexed = True

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 8, type_filter: Optional[str] = None) -> List[Dict]:
        """
        Retrieve top-k most relevant schema chunks for a query.
        
        Args:
            query: Natural language query
            k: Number of results to return
            type_filter: Optional filter on metadata type ('table_summary', 'column', 'calculation')
        
        Returns:
            List of dicts with keys: text, metadata, score
        """
        if not self._indexed or not self.documents:
            return []

        q_emb = self.model.encode([query], normalize_embeddings=True)
        scores = (self.embeddings @ q_emb.T).flatten()

        # Apply type filter
        if type_filter:
            mask = np.array([m.get("type") == type_filter for m in self.metadata])
            scores = np.where(mask, scores, -1.0)

        top_k_idx = np.argsort(scores)[::-1][:k]
        results = []
        for idx in top_k_idx:
            if scores[idx] > 0.15:  # minimum relevance threshold
                results.append({
                    "text": self.documents[idx],
                    "metadata": self.metadata[idx],
                    "score": float(scores[idx]),
                })
        return results

    def get_relevant_schema_context(self, query: str, k: int = 10) -> str:
        """
        Return a formatted string of the most relevant schema chunks for an LLM prompt.
        
        This replaces the old pattern of dumping the ENTIRE schema into every prompt.
        """
        results = self.search(query, k=k)
        if not results:
            return "No schema context available."

        lines = ["### Relevant Schema Context (retrieved by semantic similarity):"]
        seen_tables = set()

        for r in results:
            meta = r["metadata"]
            if meta["type"] == "table_summary":
                seen_tables.add(meta["table"])
                lines.append(f"\n{r['text']}")
            elif meta["type"] == "column":
                lines.append(f"  {r['text']}")
            elif meta["type"] == "calculation":
                lines.append(f"\n{r['text']}")
            elif meta["type"] == "domain":
                lines.append(f"\n{r['text']}")

        return "\n".join(lines)

    def get_relevant_tables(self, query: str, k: int = 5) -> List[str]:
        """Return table names most relevant to the query."""
        results = self.search(query, k=k * 3, type_filter="table_summary")
        tables = []
        seen = set()
        for r in results:
            t = r["metadata"].get("table")
            if t and t not in seen:
                tables.append(t)
                seen.add(t)
            if len(tables) >= k:
                break
        return tables

    @property
    def is_ready(self) -> bool:
        return self._indexed and len(self.documents) > 0
