
import os
import base64
import logging
import pymupdf
import questionary
from enum import Enum
from uuid import uuid4
from pathlib import Path
from typing import List, Optional

from openai import OpenAI as OpenAIClient
from llama_index.core.schema import Document

from src.db.models import File
from src.db.connection import Session
from src.services.index_service import IndexService
from src.config import IMAGES_TEMP_DIR, OPENAI_API_KEY, INCLUDE_IMAGE_ANALYSIS

from pydantic import BaseModel

class ImageAnalysis(BaseModel):
    image_index: int
    analysis: str

class ImageAnalysisResponse(BaseModel):
    images: List[ImageAnalysis]


logger = logging.getLogger(__name__)

class PDFService:
    
    def __init__(self, db_session: Session, index_service: IndexService = None):
        self.db = db_session
        self.index_service = index_service
        self.openai_client = OpenAIClient(api_key=OPENAI_API_KEY)
    
    class Status(Enum):
        ERROR = "error"
        SUCCESS = "success"
        OVERWRITTEN = "overwritten"
        ALREADY_EXISTS = "already_exists"
    
    def analyze_images_batch(self, images_data: List[dict], batch_size: int = 20) -> List[str]:
        all_results = []

        if not images_data:
            return []

        def chunked(iterable, size):
            for i in range(0, len(iterable), size):
                yield iterable[i:i + size]

        try:
            for batch_start_index, batch in enumerate(
                chunked(images_data, batch_size)
            ):
                content = [
                    {
                        "type": "text",
                        "text": (
                            "Analyze each image extracted from a PDF.\n"
                            "For each image:\n"
                            "- Perform OCR (extract visible text)\n"
                            "- Describe the content\n"
                            "- Explain its purpose\n"
                            "- For diagrams/graphs, explain data and relationships\n"
                        ),
                    }
                ]

                for img in batch:
                    ext = img["ext"].lower()
                    if ext == "jpg":
                        ext = "jpeg"

                    image_b64 = base64.b64encode(img["bytes"]).decode("utf-8")

                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{ext};base64,{image_b64}"
                            },
                        }
                    )

                response = self.openai_client.chat.completions.parse(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": content}],
                    response_format=ImageAnalysisResponse,
                    max_tokens=3000,
                    temperature=0,
                )

                structured = response.choices[0].message.parsed

                batch_results = {
                    img.image_index: img.analysis
                    for img in structured.images
                }

                for i in range(len(batch)):
                    all_results.append(
                        batch_results.get(i + 1, "[Analysis missing]")
                    )

            return all_results

        except Exception as e:
            logger.error(f"Error in batch image analysis: {e}", exc_info=True)
            return ["[Image analysis failed]"] * len(images_data)


    def process_pdf(self, file_path: str) -> List[Document]:

        if not isinstance(file_path, str) and not isinstance(file_path, Path):
            raise TypeError("file_path must be a string or Path.")

        doc = pymupdf.open(file_path)
        all_nodes = []
        images_to_process = []
        
        for page in doc:
            text = page.get_text().encode("utf8")
            all_nodes.append(
                Document(
                    text=text.decode("utf8"),
                    metadata={
                        "page_number": page.number + 1,
                        "file_path": str(file_path)
                    }
                )
            )
            if INCLUDE_IMAGE_ANALYSIS:
                images = page.get_images(full=True)
                for img_index, img in enumerate(images):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    images_to_process.append({
                        'bytes': base_image["image"],
                        'ext': base_image["ext"],
                        'context': text.decode("utf8"),
                        'metadata': {
                            'page_number': page.number + 1,
                            'file_path': str(file_path),
                            'image_index': img_index + 1
                        }
                    })
        
        if images_to_process:
            logger.info(f"Processing {len(images_to_process)} images in batch")
            analyses = self.analyze_images_batch(images_to_process)
            
            for idx, (img_data, analysis_text) in enumerate(zip(images_to_process, analyses)):
                all_nodes.append(
                    Document(
                        text=analysis_text,
                        metadata=img_data['metadata']
                    )
                )

        return all_nodes

    def cleanup_temp_images(self):
        try:
            if os.path.exists(IMAGES_TEMP_DIR):
                for filename in os.listdir(IMAGES_TEMP_DIR):
                    file_path = os.path.join(IMAGES_TEMP_DIR, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")
                logger.info("Cleaned up temporary images")
        except Exception as e:
            logger.warning(f"Error cleaning up temp images: {e}")
    
    def load_file(self, file_path: str) -> dict:
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            if path.suffix.lower() != '.pdf':
                raise ValueError("Only PDF files are supported")
            
            existing_file = self.db.query(File).filter(
                File.file_path == str(path.absolute())
            ).first()
            
            if existing_file:
                logger.warning(f"File {path.name} already loaded")
                
                overwrite = questionary.confirm(
                    f"File '{path.name}' is already indexed. Do you want to re-index it?",
                    default=False,
                    style=questionary.Style([
                        ('question', 'fg:cyan bold'),
                        ('answer', 'fg:green bold'),
                    ])
                ).ask()
                
                if not overwrite:
                    return {
                        "file_id": str(existing_file.id),
                        "file_name": existing_file.file_name,
                        "file_path": existing_file.file_path,
                        "status": self.Status.ALREADY_EXISTS.value
                    }
                logger.info(f"Re-indexing file: {path.name}")
                index_id = existing_file.index_id
                self.index_service.delete_index(index_id)
                is_overwrite = True
            else:
                index_id = str(uuid4())
                is_overwrite = False
            
            nodes = self.process_pdf(file_path=file_path)
            index = self.index_service.index_nodes(
                nodes = nodes,
                collection_name=index_id
            )
            
            self.cleanup_temp_images()
            
            if is_overwrite:
                existing_file.file_size = path.stat().st_size
                existing_file.file_type = 'pdf'
                self.db.commit()
                logger.info(f"Successfully re-indexed file: {path.name}")
                
                return {
                    "file_id": str(existing_file.id),
                    "file_name": existing_file.file_name,
                    "file_path": existing_file.file_path,
                    "status": self.Status.OVERWRITTEN.value
                }
            else:
                file_record = File(
                    file_name=path.name,
                    file_path=str(path.absolute()),
                    file_size=path.stat().st_size,
                    file_type='pdf',
                    index_id=index_id,
                )

                self.db.add(file_record)
                self.db.commit()
                logger.info(f"Successfully loaded file: {path.name}")
                
                return {
                    "file_id": str(file_record.id),
                    "file_name": file_record.file_name,
                    "file_path": file_record.file_path,
                    "status": self.Status.SUCCESS.value
                }
            
        except Exception as e:
            self.db.rollback()
            self.cleanup_temp_images()
            logger.error(f"Error loading file: {e}")
            raise
    
    def list_files(self) -> List[dict]:
        try:
            files = self.db.query(
                File.id,
                File.file_name,
                File.file_size,
                File.created_at,
                File.index_id
            ).order_by(File.created_at.desc()).all()
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise
    
    def get_file(self, file_id: str) -> Optional[dict]:
        try:
            
            file = self.db.query(File).filter(File.id == file_id).first()

            return {
                "file_id": str(file.id),
                "file_name": file.file_name,
                "file_path": file.file_path,
                "file_size": file.file_size,
                "created_at": file.created_at.isoformat(),
                "updated_at": file.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting file: {e}")
            raise