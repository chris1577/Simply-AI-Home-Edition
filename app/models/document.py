"""
Document models for RAG (Retrieval-Augmented Generation) functionality.
Supports document storage, chunking, and embedding references.
"""
from datetime import datetime
from app import db


class Document(db.Model):
    """
    User-uploaded document for RAG context.
    Documents are processed into chunks and embedded for semantic search.
    """

    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # File information
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)  # UUID-based filename
    file_path = db.Column(db.String(512), nullable=False)  # Relative path from uploads directory

    # File metadata
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    file_type = db.Column(db.String(20), nullable=False)  # 'pdf', 'txt', 'docx', 'xlsx', 'md', 'csv', 'json'

    # Processing status
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, processing, ready, failed
    error_message = db.Column(db.Text, nullable=True)

    # Processing metadata
    chunk_count = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    embedding_model = db.Column(db.String(100), nullable=True)  # Model used for embeddings

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)  # When processing completed

    # Relationships
    user = db.relationship('User', backref=db.backref('documents', lazy='dynamic', cascade='all, delete-orphan'))
    chunks = db.relationship('DocumentChunk', back_populates='document', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f'<Document {self.id}: {self.original_filename} ({self.status})>'

    def to_dict(self):
        """Convert document to dictionary for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'status': self.status,
            'error_message': self.error_message,
            'chunk_count': self.chunk_count,
            'total_tokens': self.total_tokens,
            'embedding_model': self.embedding_model,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'processed_at': self.processed_at.isoformat() + 'Z' if self.processed_at else None,
        }

    @property
    def is_ready(self):
        """Check if document is ready for RAG queries."""
        return self.status == 'ready'

    @property
    def is_processing(self):
        """Check if document is currently being processed."""
        return self.status == 'processing'

    @property
    def has_failed(self):
        """Check if document processing failed."""
        return self.status == 'failed'

    def mark_processing(self):
        """Mark document as currently processing."""
        self.status = 'processing'
        self.error_message = None

    def mark_ready(self, chunk_count: int, total_tokens: int, embedding_model: str):
        """Mark document as ready after successful processing."""
        self.status = 'ready'
        self.chunk_count = chunk_count
        self.total_tokens = total_tokens
        self.embedding_model = embedding_model
        self.processed_at = datetime.utcnow()
        self.error_message = None

    def mark_failed(self, error_message: str):
        """Mark document as failed with error message."""
        self.status = 'failed'
        self.error_message = error_message

    @staticmethod
    def get_file_type_from_mime(mime_type: str) -> str:
        """
        Determine file type from MIME type.

        Args:
            mime_type: MIME type string

        Returns:
            File type: 'pdf', 'txt', 'docx', 'xlsx', 'md', 'csv', 'json', or 'unknown'
        """
        mime_to_type = {
            'application/pdf': 'pdf',
            'text/plain': 'txt',
            'text/markdown': 'md',
            'text/csv': 'csv',
            'application/json': 'json',
            'application/msword': 'doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'application/vnd.ms-excel': 'xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        }
        return mime_to_type.get(mime_type, 'unknown')

    @staticmethod
    def get_supported_mime_types() -> list:
        """Return list of supported MIME types for RAG documents."""
        return [
            'application/pdf',
            'text/plain',
            'text/markdown',
            'text/csv',
            'application/json',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ]


class DocumentChunk(db.Model):
    """
    Individual chunk of a document for embedding and retrieval.
    Each chunk is stored in ChromaDB with its embedding vector.
    """

    __tablename__ = 'document_chunks'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)

    # Chunk content
    chunk_index = db.Column(db.Integer, nullable=False)  # Order within document
    content = db.Column(db.Text, nullable=False)
    token_count = db.Column(db.Integer, nullable=False)

    # Position tracking for citations
    start_char = db.Column(db.Integer, nullable=True)  # Start position in original document
    end_char = db.Column(db.Integer, nullable=True)  # End position in original document
    page_number = db.Column(db.Integer, nullable=True)  # Page number for PDFs

    # ChromaDB reference
    chroma_id = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    document = db.relationship('Document', back_populates='chunks')

    # Composite index for efficient chunk ordering
    __table_args__ = (
        db.Index('ix_document_chunks_document_index', 'document_id', 'chunk_index'),
    )

    def __repr__(self):
        return f'<DocumentChunk {self.id}: doc={self.document_id}, index={self.chunk_index}>'

    def to_dict(self):
        """Convert chunk to dictionary for API responses."""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'chunk_index': self.chunk_index,
            'content': self.content,
            'token_count': self.token_count,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'page_number': self.page_number,
            'chroma_id': self.chroma_id,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }

    def to_retrieval_dict(self):
        """Convert chunk to dictionary for RAG retrieval responses."""
        doc = self.document
        return {
            'content': self.content,
            'document_id': self.document_id,
            'document_name': doc.original_filename if doc else None,
            'chunk_index': self.chunk_index,
            'page_number': self.page_number,
            'token_count': self.token_count,
        }
