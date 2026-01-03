import logging
from typing import List

from sqlalchemy import text
from llama_index.core.schema import Node
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import VectorStoreIndex, Settings, StorageContext

from src.db.connection import Session
from src.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

class IndexService:
    
    def __init__(self, openai_api_key: str, db_session: Session, model: str = "text-embedding-3-small"):
        self.db = db_session
        Settings.embed_model = OpenAIEmbedding(
            model="text-embedding-3-small", 
            api_key=openai_api_key,
            dimensions=1536,
        )
        
        Settings.llm = OpenAI(
            model="gpt-4o",
            api_key=openai_api_key,
            temperature=0,
        )
        logger.info("IndexService initialized")
    
    def get_or_create_vector_store(self, collection_name: str) -> PGVectorStore:
        vector_store = PGVectorStore.from_params(
            database=DB_NAME,
            host=DB_HOST,
            password=DB_PASSWORD,
            port=DB_PORT,
            user=DB_USER,
            table_name=f"llamaindex_{collection_name}",
            embed_dim=1536
        )
        return vector_store
    
    def _get_collection_table_name(self, collection_name: str) -> str:
        return f"data_llamaindex_{collection_name}"

    def index_nodes(
        self, 
        nodes: List[Node],
        collection_name: str,
    ) -> None:
        try:
            vector_store = self.get_or_create_vector_store(collection_name)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex(
                nodes, 
                storage_context=storage_context,
                show_progress=True
            )
            logger.info(f"Successfully indexed {len(nodes)} nodes to {collection_name}")
            return index
        except Exception as e:
            logger.error(f"Error loading and indexing PDF: {e}")
            raise
            
    def load_index(self, collection_name: str) -> VectorStoreIndex:
        try:
            vector_store = self.get_or_create_vector_store(collection_name)
            index = VectorStoreIndex.from_vector_store(vector_store)
            logger.info(f"Loaded index for collection: {collection_name}")
            return index
        except Exception as e:
            raise

    def delete_index(self, collection_name: str) -> None:
        try:
            self.db.execute(text(f'DELETE FROM "{self._get_collection_table_name(collection_name)}";'))
            self.db.commit()
            logger.info(f"Deleted index and table for collection: {collection_name}")
        except Exception as e:
            logger.error(f"Error deleting index for collection {collection_name}: {e}")
            raise