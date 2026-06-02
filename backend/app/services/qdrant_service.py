from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Dict, Optional
import uuid
from app.core.config import settings


class QdrantService:
    def __init__(self):
        print(f"[Qdrant] Connecting to {settings.QDRANT_URL}...")
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=30,
            prefer_grpc=False,
            check_compatibility=False
        )
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = 768  # nomic-embed-text from Ollama
        
        # Initialize collection on startup
        self._ensure_collection()
        print(f"[Qdrant] Connected successfully! Collection: {self.collection_name}")
    
    def _ensure_collection(self):
        """Ensure the collection exists, create if not"""
        try:
            # collection_exists() is less likely to trigger generic 404s than full metadata checks
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
                print(f"[Qdrant] Created collection: {self.collection_name}")
        except Exception as e:
            # Log the specific error for debugging but don't crash
            print(f"[Qdrant] Warning: Could not verify collection '{self.collection_name}'. Error: {type(e).__name__}: {e}")
    
    def create_collection(self):
        """Explicitly create collection (deprecated, use _ensure_collection)"""
        self._ensure_collection()
    
    def insert_part(self, embedding: List[float], payload: Dict) -> str:
        point_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )]
        )
        return point_id
    
    def search_parts(self, query_vector: List[float], limit: int = 5, 
                     supplier: Optional[str] = None, 
                     transmission_code: Optional[str] = None,
                     part_type: Optional[str] = None,
                     document_ids: Optional[List[str]] = None) -> List[Dict]:
        search_filter = None
        
        if supplier or transmission_code or part_type or document_ids:
            conditions = []
            if supplier:
                conditions.append(FieldCondition(key="supplier", match=MatchValue(value=supplier)))
            if transmission_code:
                conditions.append(FieldCondition(key="transmission_code", match=MatchValue(value=transmission_code)))
            if part_type:
                conditions.append(FieldCondition(key="part_type", match=MatchValue(value=part_type)))
            if document_ids:
                from qdrant_client.models import MatchAny
                conditions.append(FieldCondition(key="document_id", match=MatchAny(any=document_ids)))
            
            if conditions:
                search_filter = Filter(must=conditions)
        
        # Use query_points for newer qdrant-client versions
        try:
            # Try newer API first (qdrant-client >= 1.7.0)
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=search_filter,
                limit=limit,
                with_payload=True
            ).points
        except AttributeError:
            # Fallback to older API
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=limit,
                with_payload=True
            )
        
        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload
            }
            for r in results
        ]
    
    def delete_by_supplier(self, supplier_name: str):
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="supplier", match=MatchValue(value=supplier_name))]
            )
        )


qdrant_service = QdrantService()
