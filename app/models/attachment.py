"""
Attachment model for file attachments in chat messages.
Supports images, PDFs, and other document types.
"""
from datetime import datetime
from app import db


class Attachment(db.Model):
    """Model for file attachments linked to chat messages."""

    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False)

    # File information
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)  # UUID-based filename
    file_path = db.Column(db.String(512), nullable=False)  # Relative path from uploads directory

    # File metadata
    mime_type = db.Column(db.String(100), nullable=False)  # e.g., image/png, application/pdf
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    file_type = db.Column(db.String(20), nullable=False)  # 'image', 'document', 'other'

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    message = db.relationship('Message', back_populates='attachments')

    def __repr__(self):
        return f'<Attachment {self.id}: {self.original_filename}>'

    def to_dict(self):
        """Convert attachment to dictionary for API responses."""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'original_filename': self.original_filename,
            'stored_filename': self.stored_filename,
            'file_path': self.file_path,  # Required for AI service to read file
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'url': f'/api/attachments/{self.id}'  # URL to download/view the file
        }

    @property
    def is_image(self):
        """Check if attachment is an image."""
        return self.file_type == 'image'

    @property
    def is_document(self):
        """Check if attachment is a document."""
        return self.file_type == 'document'

    @staticmethod
    def get_file_type(mime_type: str) -> str:
        """
        Determine file type category from MIME type.

        Args:
            mime_type: MIME type string (e.g., 'image/png')

        Returns:
            File type category: 'image', 'document', or 'other'
        """
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type in ['application/pdf', 'application/msword',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'application/vnd.ms-excel',
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          'text/plain', 'text/csv', 'text/markdown']:
            return 'document'
        else:
            return 'other'
