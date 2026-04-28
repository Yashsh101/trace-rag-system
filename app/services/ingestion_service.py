from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationAppError
from app.models.chunk import Chunk
from app.models.document import Document, DocumentVersion
from app.services.chunker import CHUNKER_VERSION, Chunker
from app.services.embedding_service import EmbeddingService
from app.services.pdf_parser import PARSER_VERSION, PDFParser
from app.services.storage import StorageBackend, build_storage_backend
from app.utils.hash import sha256_bytes


PDF_MAGIC = b"%PDF-"


class IngestionService:
    def __init__(
        self,
        parser: PDFParser | None = None,
        chunker: Chunker | None = None,
        embedding_service: EmbeddingService | None = None,
        storage_backend: StorageBackend | None = None,
    ):
        self.parser = parser or PDFParser()
        self.chunker = chunker or Chunker()
        self.embedding_service = embedding_service or EmbeddingService()
        self.storage_backend = storage_backend or build_storage_backend()

    def ingest_pdf(self, db: Session, filename: str, content_type: str, content: bytes) -> tuple[Document, DocumentVersion, int]:
        return self.ingest_pdf_with_acl(
            db=db,
            filename=filename,
            content_type=content_type,
            content=content,
            owner_id=None,
            visibility="private",
            allowed_user_ids=[],
            allowed_group_ids=[],
        )

    def ingest_pdf_with_acl(
        self,
        db: Session,
        filename: str,
        content_type: str,
        content: bytes,
        owner_id: str | None,
        visibility: str = "private",
        allowed_user_ids: list[str] | None = None,
        allowed_group_ids: list[str] | None = None,
        raw_file_uri: str | None = None,
    ) -> tuple[Document, DocumentVersion, int]:
        try:
            self._validate_pdf_upload(filename=filename, content_type=content_type, content=content)

            content_hash = sha256_bytes(content)
            existing = db.execute(
                select(Document).where(Document.content_hash == content_hash, Document.owner_id == owner_id)
            ).scalar_one_or_none()
            if existing:
                version = db.execute(
                    select(DocumentVersion).where(DocumentVersion.document_id == existing.id, DocumentVersion.active.is_(True))
                ).scalar_one()
                chunk_count = db.scalar(select(func.count(Chunk.id)).where(Chunk.document_version_id == version.id)) or 0
                return existing, version, int(chunk_count)

            pages = self.parser.parse(content)
            parsed_text = "\n\n".join(f"Page {page.page_number}\n{page.text}" for page in pages)
            text_chunks = self.chunker.chunk_pages(pages)
            if not text_chunks:
                raise ValidationAppError("No chunks were produced from the PDF")

            embeddings = self.embedding_service.embed_texts([chunk.text for chunk in text_chunks])
            raw_file_uri = raw_file_uri or self.storage_backend.put_bytes(
                key=f"raw/{content_hash}/{filename}",
                content=content,
                content_type=content_type or "application/pdf",
            )
            parsed_text_uri = self.storage_backend.put_bytes(
                key=f"parsed/{content_hash}/parsed.txt",
                content=parsed_text.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
            )

            document = Document(
                filename=filename,
                content_type=content_type or "application/pdf",
                content_hash=content_hash,
                raw_file_uri=raw_file_uri,
                storage_backend=self.storage_backend.name,
                file_size_bytes=len(content),
                owner_id=owner_id,
                visibility=visibility,
                allowed_user_ids=allowed_user_ids or [],
                allowed_group_ids=allowed_group_ids or [],
            )
            db.add(document)
            db.flush()

            version = DocumentVersion(
                document_id=document.id,
                version=1,
                parser_version=PARSER_VERSION,
                chunker_version=CHUNKER_VERSION,
                embedding_model=settings.openai_embedding_model,
                embedding_dimension=settings.embedding_dimension,
                status="completed",
                active=True,
                parsed_text_uri=parsed_text_uri,
            )
            db.add(version)
            db.flush()

            for text_chunk, embedding in zip(text_chunks, embeddings, strict=True):
                db.add(
                    Chunk(
                        document_id=document.id,
                        document_version_id=version.id,
                        chunk_index=text_chunk.chunk_index,
                        text=text_chunk.text,
                        token_count=text_chunk.token_count,
                        page_start=text_chunk.page_start,
                        page_end=text_chunk.page_end,
                        embedding=embedding,
                        metadata_json=text_chunk.metadata,
                    )
                )

            db.commit()
            db.refresh(document)
            db.refresh(version)
            return document, version, len(text_chunks)
        except Exception:
            db.rollback()
            raise

    def _validate_pdf_upload(self, filename: str, content_type: str, content: bytes) -> None:
        if not content:
            raise ValidationAppError("Uploaded PDF is empty")
        if len(content) > settings.max_upload_bytes:
            raise ValidationAppError(f"File exceeds max upload size of {settings.max_upload_mb} MB")
        if not filename.lower().endswith(".pdf"):
            raise ValidationAppError("Only .pdf files are supported in v1")
        if content_type and content_type not in settings.allowed_pdf_content_types:
            raise ValidationAppError("Uploaded file content type must be application/pdf")
        if not content.startswith(PDF_MAGIC):
            raise ValidationAppError("Uploaded file does not look like a PDF")
