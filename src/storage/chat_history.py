"""
Chat History Storage with PostgreSQL and pgvector.
Stores chat messages as vector embeddings for semantic search.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import numpy as np


class ChatHistoryStore:
    """Store and retrieve chat history with vector embeddings."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize chat history store.
        
        Args:
            host: PostgreSQL host (default: from env or localhost)
            port: PostgreSQL port (default: from env or 5432)
            database: Database name (default: from env or agentic_rag)
            user: Database user (default: from env or postgres)
            password: Database password (default: from env)
            embedding_model: Sentence transformer model for embeddings
        """
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port or int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = database or os.getenv("POSTGRES_DB", "agentic_rag")
        self.user = user or os.getenv("POSTGRES_USER", "postgres")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "postgres")
        
        # Initialize embedding model
        print(f"[INFO] Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        
        # Initialize database connection
        self.conn = None
        self._connect()
        self._ensure_extension()
        self._create_tables()
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            print(f"[INFO] Connected to PostgreSQL at {self.host}:{self.port}/{self.database}")
        except psycopg2.OperationalError as e:
            print(f"[WARNING] Could not connect to PostgreSQL: {e}")
            print("[INFO] Chat history will not be persisted. To enable:")
            print("  1. Install PostgreSQL: https://www.postgresql.org/download/")
            print("  2. Create database: createdb agentic_rag")
            print("  3. Set POSTGRES_* env variables in .env")
            self.conn = None
    
    def _ensure_extension(self):
        """Ensure pgvector extension is installed."""
        if not self.conn:
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                self.conn.commit()
                print("[INFO] pgvector extension enabled")
        except Exception as e:
            print(f"[WARNING] Could not enable pgvector extension: {e}")
            print("[INFO] Install pgvector: https://github.com/pgvector/pgvector")
    
    def _create_tables(self):
        """Create chat history tables if they don't exist."""
        if not self.conn:
            return
        
        try:
            with self.conn.cursor() as cur:
                # Sessions table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        session_id VARCHAR(255) PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    )
                """)
                
                # Messages table with vector embeddings
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(255) REFERENCES chat_sessions(session_id),
                        role VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector({self.embedding_dim}),
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index for vector similarity search
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS chat_messages_embedding_idx 
                    ON chat_messages USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                
                self.conn.commit()
                print("[INFO] Chat history tables created/verified")
        except Exception as e:
            print(f"[ERROR] Could not create tables: {e}")
            self.conn.rollback()
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def create_session(self, session_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Create a new chat session."""
        if not self.conn:
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, metadata)
                    VALUES (%s, %s)
                    ON CONFLICT (session_id) DO UPDATE
                    SET updated_at = CURRENT_TIMESTAMP
                    """,
                    (session_id, json.dumps(metadata or {}))
                )
                self.conn.commit()
        except Exception as e:
            print(f"[ERROR] Could not create session: {e}")
            self.conn.rollback()
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Add a message to chat history with vector embedding.
        
        Args:
            session_id: Session identifier
            role: Message role (user/assistant)
            content: Message content
            metadata: Additional metadata (query results, SQL, etc.)
            
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.conn:
            return None
        
        try:
            # Generate embedding
            embedding = self._generate_embedding(content)
            
            with self.conn.cursor() as cur:
                # Ensure session exists
                self.create_session(session_id)
                
                # Insert message
                cur.execute(
                    """
                    INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (session_id, role, content, embedding, json.dumps(metadata or {}))
                )
                message_id = cur.fetchone()[0]
                self.conn.commit()
                
                print(f"[INFO] Saved message {message_id} to chat history")
                return message_id
        except Exception as e:
            print(f"[ERROR] Could not add message: {e}")
            self.conn.rollback()
            return None
    
    def get_session_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get chat history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of messages
        """
        if not self.conn:
            return []
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT id, role, content, metadata, created_at
                    FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                cur.execute(query, (session_id,))
                messages = cur.fetchall()
                
                return [dict(msg) for msg in messages]
        except Exception as e:
            print(f"[ERROR] Could not fetch session history: {e}")
            return []
    
    def search_similar_messages(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar messages using vector similarity.
        
        Args:
            query: Search query
            session_id: Optional session to filter by
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity (0-1)
            
        Returns:
            List of similar messages with similarity scores
        """
        if not self.conn:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query)
            
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                query_sql = """
                    SELECT 
                        id, session_id, role, content, metadata, created_at,
                        1 - (embedding <=> %s::vector) as similarity
                    FROM chat_messages
                """
                
                params = [query_embedding]
                
                if session_id:
                    query_sql += " WHERE session_id = %s"
                    params.append(session_id)
                
                query_sql += """
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """
                params.extend([query_embedding, limit])
                
                cur.execute(query_sql, params)
                results = cur.fetchall()
                
                # Filter by similarity threshold
                filtered_results = [
                    dict(msg) for msg in results 
                    if msg['similarity'] >= similarity_threshold
                ]
                
                return filtered_results
        except Exception as e:
            print(f"[ERROR] Could not search similar messages: {e}")
            return []
    
    def get_recent_context(
        self,
        session_id: str,
        limit: int = 5
    ) -> str:
        """
        Get recent conversation context as formatted string.
        
        Args:
            session_id: Session identifier
            limit: Number of recent messages
            
        Returns:
            Formatted conversation context
        """
        messages = self.get_session_history(session_id, limit=limit)
        
        if not messages:
            return ""
        
        context_parts = []
        for msg in messages:
            role = msg['role'].upper()
            content = msg['content']
            context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)
    
    def delete_session(self, session_id: str):
        """Delete a chat session and all its messages."""
        if not self.conn:
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))
                cur.execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
                self.conn.commit()
                print(f"[INFO] Deleted session {session_id}")
        except Exception as e:
            print(f"[ERROR] Could not delete session: {e}")
            self.conn.rollback()
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all chat sessions."""
        if not self.conn:
            return []
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT session_id, created_at, updated_at, metadata,
                           (SELECT COUNT(*) FROM chat_messages WHERE session_id = chat_sessions.session_id) as message_count
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                """)
                sessions = cur.fetchall()
                return [dict(s) for s in sessions]
        except Exception as e:
            print(f"[ERROR] Could not fetch sessions: {e}")
            return []
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("[INFO] PostgreSQL connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
