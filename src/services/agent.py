import logging
from datetime import datetime
from typing import List, Dict
from src.db.models import File
from .index_service import IndexService
from .cache_service import CacheService
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.base.llms.types import ChatMessage

logger = logging.getLogger(__name__)

class InspectorAgent:

    def __init__( self, index_service: IndexService, cache_service: CacheService):
        self.index_service = index_service
        self.cache_service = cache_service
        self.file_sessions: Dict[str, Dict] = {}
        
        logger.info("InspectorAgent initialized")
    
    def _get_history_key(self, file_id: str) -> str:
        return f"agent:history:{file_id}"
    
    def _load_chat_history(self, file_id: str) -> List[Dict]:
        history = self.cache_service.get(self._get_history_key(file_id))
        return history if history else []
    
    def _save_chat_history(self, file_id: str, history: List[Dict]) -> bool:
        return self.cache_service.set(
            self._get_history_key(file_id),
            history,
            ttl=7200
        )
    
    def _get_or_create_session(self, file: File) -> Dict:
        if file.id in self.file_sessions:
            return self.file_sessions[file.id]

        index = self.index_service.load_index(file.index_id)
        history = self._load_chat_history(file.id)
        memory = ChatMemoryBuffer(token_limit=4000)
        if history:
            for msg in history:
                memory.put(ChatMessage(
                    role=msg["role"],
                    content=msg["content"]
                ))
            logger.info(f"Loaded {len(history)} messages from chat history for file {file.id}")

        session_data = {
            "history": history,
            "chat_engine": index.as_chat_engine(
                similarity_top_k=10,
                chat_mode="condense_plus_context",
                memory=memory
            ),
        }
        
        self.file_sessions[file.id] = session_data
        return session_data
    
    def query(self, question: str, file: File) -> Dict:
        try:
            session_data = self._get_or_create_session(file)
            history = session_data["history"]
            response = session_data["chat_engine"].chat(question)
            answer = str(response)
            
            history.append({
                "role": "user",
                "content": question,
                "timestamp": datetime.now().isoformat()
            })
            history.append({
                "role": "assistant",
                "content": answer,
                "timestamp": datetime.now().isoformat()
            })
            
            session_data["history"] = history
            self._save_chat_history(file.id, history)
            
            result = {
                "answer": answer,
                "cached": False,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            raise
    
    def clear_session(self, file_id: str) -> bool:
        try:
            if file_id in self.file_sessions:
                del self.file_sessions[file_id]
            
            self.cache_service.delete(self._get_history_key(file_id))
            return True
            
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False
    
    def get_chat_history(self, file_id: str) -> List[Dict]:
        return self._load_chat_history(file_id)