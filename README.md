# Inspector CLI

**Intelligent PDF Document Analysis System with RAG and Vision AI**

Inspector CLI is a powerful document analysis tool that combines PDF processing, vector search, and multi-modal AI to provide intelligent question-answering capabilities over your documents. It extracts text and images, uses OpenAI's Vision API for OCR and image analysis, and maintains conversational context through chat history.


The application can run in two modes:
1. **Interactive CLI** - Direct terminal usage for document management and querying
2. **MCP Server** - Integration with AI assistants like Claude Desktop


### Declaring Usage of AI

- **Terminal Interface**: The interactive CLI using `questionary` and `rich` libraries was designed and implemented with AI assistance to provide an intuitive user experience
- **Documentation**: This README was created with AI assistance to ensure comprehensive coverage and clarity.

## Installation

### Prerequisites

- Python 3.13 or higher
- Docker and Docker Compose (for database services)
- OpenAI API key

### Quick Setup with Docker

The easiest way to get started is using Docker Compose for PostgreSQL and Redis:

1. Clone the repository:
```bash
git clone <repository-url>
cd inspector-cli
```

2. Start database services:
```bash
docker-compose up -d
```

This starts:
- PostgreSQL 18 with pgvector extension on port 5432
- Redis 7 with persistence on port 6379

3. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` with your OpenAI API key. Database defaults work with Docker Compose:
```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=inspector
REDIS_HOST=localhost
REDIS_PORT=6379
OPENAI_API_KEY=your-api-key-here
```

4. Install Python dependencies and the CLI:
```bash
poetry install
```

Or using pip (to make `inspector` command available globally):
```bash
pip install -e .
```

5. Run database migrations:
```bash
alembic upgrade head
```

6. Start using Inspector:
```bash
inspector
```

If you installed with Poetry, use:
```bash
poetry run inspector
```

### Manual Installation (Without Docker)

If you prefer installing PostgreSQL and Redis manually:

**System Dependencies:**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib redis-server python3-dev
sudo apt install postgresql-14-pgvector
```

**macOS:**
```bash
brew install postgresql redis pgvector
brew services start postgresql
brew services start redis
```

**Database Setup:**

1. Create database:
```bash
createdb inspector
```

2. Enable pgvector extension:
```bash
psql inspector -c "CREATE EXTENSION vector;"
```

3. Follow steps 3-6 from Quick Setup above

### Installing the CLI Command

To make the `inspector` command available globally in your terminal:

```bash
# Using pip (recommended for direct CLI access)
pip install -e .

# Then you can run from anywhere
inspector
```

Or use Poetry:

```bash
# With Poetry, prefix commands with 'poetry run'
poetry install
poetry run inspector
```

## CLI Usage

### Interactive Mode

Start the interactive terminal interface:

```bash
inspector
```

Or with Poetry:
```bash
poetry run inspector
```

Or using Poetry:
```bash
poetry run inspector
```

### Main Menu Options

The interactive interface provides three main options:

#### 1. Load New File

Load and index a PDF document:
- Navigate with arrow keys
- Enter the absolute path to your PDF file
- The system will:
  - Extract text from all pages
  - Extract and analyze all images in a single batch
  - Create vector embeddings
  - Store in PostgreSQL

**Example:**
```
What would you like to do?
> Load new file
  Query existing file
  Exit

Enter the path to your PDF file: /home/user/documents/research.pdf

Loading file: /home/user/documents/research.pdf
Processing 45 images in batch...
✓ Successfully loaded file!
File ID: abc-123-def-456
File Name: research.pdf
```

#### 2. Query Existing File

Ask questions about indexed documents:
- Select a file from the list
- Enter your questions in natural language
- View AI-generated answers based on document content
- Chat history is maintained for context

**Example:**
```
Select a file to query:
> research.pdf (ID: abc-123)
  book.pdf (ID: def-456)
  ← Back to main menu

Your question: What are the main findings?

Answer:
The main findings indicate that...
[Detailed answer based on document content]

Your question: Can you elaborate on the methodology?
[Context from previous question is maintained]

Commands:
- Type 'exit' or 'quit' to return to main menu
- Type 'clear' to clear chat history
```

#### 3. File Management

The system automatically handles:
- **Duplicate Detection** - Prompts if file already exists
- **Re-indexing** - Option to overwrite existing index
- **Chat History** - Persisted per document in Redis
- **Vector Cleanup** - Removes old embeddings on re-index

## MCP Usage

Model Context Protocol (MCP) allows AI assistants like Claude to interact with your document collection.

### Setup for Claude Desktop

1. Locate your Claude Desktop configuration:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux:** `~/.config/Claude/claude_desktop_config.json`

2. Add Inspector CLI server:

```json
{
  "mcpServers": {
    "inspector-cli": {
      "command": "/full/path/to/inspector-cli/.venv/bin/inspector-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key"
      }
    }
  }
}
```

Or using Poetry:

```json
{
  "mcpServers": {
    "inspector-cli": {
      "command": "poetry",
      "args": ["run", "inspector-mcp"],
      "cwd": "/full/path/to/inspector-cli",
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key"
      }
    }
  }
}
```

3. Restart Claude Desktop

### Available MCP Tools

Once connected, Claude can use these tools:

#### `load_pdf`
Load and index a PDF file.

**Parameters:**
- `file_path` (string, required) - Absolute path to the PDF file

**Example:**
```
User: Please load the PDF at /home/user/reports/Q4-2025.pdf
Claude: [Uses load_pdf tool]
✓ Successfully loaded and indexed file!
File ID: xyz-789
```

#### `list_files`
List all indexed PDF files.

**Parameters:** None

**Example:**
```
User: What documents do I have indexed?
Claude: [Uses list_files tool]
Indexed Files:
• research.pdf (ID: abc-123, Size: 2.5 MB)
• report.pdf (ID: def-456, Size: 1.8 MB)
```

#### `get_file`
Get detailed information about a specific file.

**Parameters:**
- `file_id` (string, required) - UUID of the file

#### `delete_file`
Delete an indexed file from the system.

**Parameters:**
- `file_id` (string, required) - UUID of the file

#### `query_file`
Ask questions about a PDF document.

**Parameters:**
- `file_id` (string, required) - UUID of the file
- `question` (string, required) - The question to ask

**Example:**
```
User: What are the key conclusions in file abc-123?
Claude: [Uses query_file tool]
Based on the document, the key conclusions are...
```

#### `get_chat_history`
Retrieve conversation history for a file.

**Parameters:**
- `file_id` (string, required) - UUID of the file

#### `clear_chat_history`
Clear conversation history for a file.

**Parameters:**
- `file_id` (string, required) - UUID of the file

### Running MCP Server Manually

Start the MCP server directly:

```bash
inspector-mcp
```

Or:
```bash
poetry run inspector-mcp
```

The server communicates via stdio and is designed to be used by MCP clients.

## Environment Variables

Create a `.env` file in the project root with the following variables:

### Required Variables

```bash
# OpenAI API Key (required for embeddings and vision)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-database-password
DB_NAME=inspector
```

### Optional Variables

```bash
# Redis Configuration (optional - for caching and chat history)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Environment Variable Details

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings and vision | - | Yes |
| `DB_HOST` | PostgreSQL host address | localhost | Yes |
| `DB_PORT` | PostgreSQL port | 5432 | Yes |
| `DB_USER` | PostgreSQL username | postgres | Yes |
| `DB_PASSWORD` | PostgreSQL password | - | Yes |
| `DB_NAME` | PostgreSQL database name | inspector | Yes |
| `REDIS_HOST` | Redis host address | localhost | No |
| `REDIS_PORT` | Redis port | 6379 | No |
| `REDIS_DB` | Redis database number | 0 | No |

**Note:** Redis is optional. If not available, the system will log a warning and disable caching, but will continue to function normally.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Inspector CLI Application              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────┐         ┌──────────────────┐   │
│  │ Interactive CLI │         │   MCP Server     │   │
│  │  (Questionary)  │         │ (stdio protocol) │   │
│  └────────┬────────┘         └────────┬─────────┘   │
│           │                           │             │
│           └──────────┬────────────────┘             │
│                      │                              │
│         ┌────────────▼────────────┐                 │
│         │    Service Layer        │                 │
│         │  • PdfService           │                 │
│         │  • IndexService         │                 │
│         │  • InspectorAgent       │                 │
│         │  • CacheService         │                 │
│         └────────────┬────────────┘                 │
│                      │                              │
└──────────────────────┼──────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼─────┐   ┌────▼─────┐   ┌────▼────┐
   │PostgreSQL│   │  Redis   │   │ OpenAI  │
   │          │   │          │   │         │
   │• Vector  │   │• Cache   │   │• GPT-4o │
   │  Store   │   │• Chat    │   │• Vision │
   │• Metadata│   │  History │   │• Embed  │
   └──────────┘   └──────────┘   └─────────┘
```

## Development

### Project Structure

```
inspector-cli/
├── src/
│   ├── config.py              # Configuration and environment
│   ├── main.py                # CLI entry point
│   ├── interactive.py         # Interactive interface
│   ├── mcp_server.py          # MCP server implementation
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models
│   │   └── connection.py      # Database connection
│   └── services/
│       ├── file_service.py    # PDF processing and indexing
│       ├── index_service.py   # Vector store and embeddings
│       ├── agent.py           # RAG agent with chat history
│       └── cache_service.py   # Redis caching layer
├── alembic/                   # Database migrations
├── temp/                      # Temporary image storage
├── pyproject.toml            # Project dependencies
├── .env                      # Environment configuration
└── README.md                 # This file
```

## Troubleshooting

### Database Connection Error
```
Error: Could not connect to database
```
**Solution:** Ensure PostgreSQL is running and credentials in `.env` are correct.

### Redis Warning
```
Could not connect to Redis. Caching will be disabled.
```
**Solution:** Redis is optional. Start Redis server or ignore the warning.

### Import Errors
```
ModuleNotFoundError: No module named 'mcp'
```
**Solution:** Run `poetry install` to install all dependencies.