import logging
import asyncio
from typing import Any

from mcp import types
from mcp.server.stdio import stdio_server
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from src.db.models import File
from src.db.connection import get_db
from src.services.index_service import IndexService
from src.services import PDFService, CacheService, InspectorAgent
from src.config import REDIS_HOST, REDIS_PORT, REDIS_DB, OPENAI_API_KEY

logger = logging.getLogger(__name__)

db = None
index_service = None
file_service = None
cache_service = None
agent = None

def initialize_services():
    global db, index_service, file_service, cache_service, agent
    
    try:
        db = get_db()
        if not db:
            raise Exception("Failed to connect to database")
        
        index_service = IndexService(OPENAI_API_KEY, db)
        file_service = PDFService(db, index_service)
        cache_service = CacheService(REDIS_HOST, REDIS_PORT, REDIS_DB)
        agent = InspectorAgent(index_service, cache_service)
        
        logger.info("All services initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        return False

server = Server("inspector-cli")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="load_pdf",
            description="Load and index a PDF file for analysis. The file will be processed, embedded, and stored in the vector database for querying.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the PDF file to load and index"
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="list_files",
            description="List all indexed PDF files with their metadata including file name, size, and creation date.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_file",
            description="Get detailed information about a specific indexed file including its path, size, and timestamps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "UUID of the file to retrieve information for"
                    }
                },
                "required": ["file_id"]
            }
        ),
        types.Tool(
            name="delete_file",
            description="Delete an indexed file from the system. This removes the file from the database but does not delete the original PDF.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "UUID of the file to delete"
                    }
                },
                "required": ["file_id"]
            }
        ),
        types.Tool(
            name="query_file",
            description="Ask a question about a specific indexed PDF file. Uses RAG (Retrieval Augmented Generation) to provide accurate answers based on the document content. Maintains conversation history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "UUID of the file to query"
                    },
                    "question": {
                        "type": "string",
                        "description": "The question to ask about the document"
                    }
                },
                "required": ["file_id", "question"]
            }
        ),
        types.Tool(
            name="get_chat_history",
            description="Retrieve the conversation history for a specific file, showing all previous questions and answers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "UUID of the file to get chat history for"
                    }
                },
                "required": ["file_id"]
            }
        ),
        types.Tool(
            name="clear_chat_history",
            description="Clear the conversation history for a specific file, starting fresh with no context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "UUID of the file to clear chat history for"
                    }
                },
                "required": ["file_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    try:
        if name == "load_pdf":
            file_path = arguments.get("file_path")
            if not file_path:
                return [types.TextContent(
                    type="text",
                    text="Error: file_path is required"
                )]
            
            result = file_service.load_file(file_path, interactive=False)
            
            if result["status"] == "success":
                response = f"✓ Successfully loaded and indexed file!\n\nFile ID: {result['file_id']}\nFile Name: {result['file_name']}\nFile Path: {result['file_path']}"
            elif result["status"] == "already_exists":
                response = f"File already indexed.\n\nFile ID: {result['file_id']}\nFile Name: {result['file_name']}\n\nUse delete_file first if you want to re-index it."
            elif result["status"] == "overwritten":
                response = f"✓ Successfully re-indexed file!\n\nFile ID: {result['file_id']}\nFile Name: {result['file_name']}"
            else:
                response = f"Error: Unknown status {result['status']}"
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "list_files":
            files = file_service.list_files()
            
            if not files:
                return [types.TextContent(
                    type="text",
                    text="No files have been indexed yet."
                )]
            
            response_lines = ["Indexed Files:\n"]
            for file in files:
                response_lines.append(
                    f"• {file.file_name}\n"
                    f"  ID: {file.id}\n"
                    f"  Size: {file.file_size:,} bytes\n"
                    f"  Created: {file.created_at}\n"
                )
            
            return [types.TextContent(
                type="text",
                text="\n".join(response_lines)
            )]
        
        elif name == "get_file":
            file_id = arguments.get("file_id")
            if not file_id:
                return [types.TextContent(
                    type="text",
                    text="Error: file_id is required"
                )]
            
            file_info = file_service.get_file(file_id)
            
            if not file_info:
                return [types.TextContent(
                    type="text",
                    text=f"Error: File with ID {file_id} not found"
                )]
            
            response = (
                f"File Information:\n\n"
                f"Name: {file_info['file_name']}\n"
                f"Path: {file_info['file_path']}\n"
                f"Size: {file_info['file_size']:,} bytes\n"
                f"Created: {file_info['created_at']}\n"
                f"Updated: {file_info['updated_at']}"
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "delete_file":
            file_id = arguments.get("file_id")
            if not file_id:
                return [types.TextContent(
                    type="text",
                    text="Error: file_id is required"
                )]
            
            success = file_service.delete_file(file_id)
            
            if success:
                response = f"✓ Successfully deleted file with ID: {file_id}"
            else:
                response = f"Error: File with ID {file_id} not found"
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "query_file":
            file_id = arguments.get("file_id")
            question = arguments.get("question")
            
            if not file_id or not question:
                return [types.TextContent(
                    type="text",
                    text="Error: Both file_id and question are required"
                )]
            
            file = db.query(File).filter(File.id == file_id).first()
            
            if not file:
                return [types.TextContent(
                    type="text",
                    text=f"Error: File with ID {file_id} not found"
                )]
            
            result = agent.query(question=question, file=file)
            
            response = f"Question: {question}\n\nAnswer:\n{result['answer']}"
            
            if result.get("cached"):
                response += "\n\n(Cached result)"
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "get_chat_history":
            file_id = arguments.get("file_id")
            if not file_id:
                return [types.TextContent(
                    type="text",
                    text="Error: file_id is required"
                )]
            
            history = agent.get_chat_history(file_id)
            
            if not history:
                return [types.TextContent(
                    type="text",
                    text="No chat history found for this file."
                )]
            
            response_lines = ["Chat History:\n"]
            for msg in history:
                role = "You" if msg["role"] == "user" else "Assistant"
                response_lines.append(f"\n{role}: {msg['content']}")
                if "timestamp" in msg:
                    response_lines.append(f"  ({msg['timestamp']})")
            
            return [types.TextContent(
                type="text",
                text="\n".join(response_lines)
            )]
        
        elif name == "clear_chat_history":
            file_id = arguments.get("file_id")
            if not file_id:
                return [types.TextContent(
                    type="text",
                    text="Error: file_id is required"
                )]
            
            success = agent.clear_session(file_id)
            
            if success:
                response = f"✓ Successfully cleared chat history for file: {file_id}"
            else:
                response = f"Error: Could not clear chat history for file: {file_id}"
            
            return [types.TextContent(type="text", text=response)]
        
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown tool '{name}'"
            )]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error executing tool: {str(e)}"
        )]

async def main():
    if not initialize_services():
        logger.error("Failed to initialize services. Exiting.")
        return
    
    logger.info("Starting Inspector CLI MCP Server...")
    
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="inspector-cli",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        )
        
        await server.run(
            read_stream,
            write_stream,
            init_options
        )

def run_server():
    asyncio.run(main())

if __name__ == "__main__":
    run_server()
