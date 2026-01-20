"""
File upload and management service.
Handles secure file storage, validation, and retrieval.
"""
import os
import uuid
import mimetypes
from pathlib import Path
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from typing import Tuple, Optional


class FileService:
    """Service for handling file uploads and storage."""

    # Allowed file extensions and MIME types
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.txt', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.md'}
    ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS

    # MIME type mappings
    ALLOWED_MIME_TYPES = {
        # Images
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
        # Documents
        'application/pdf',
        'text/plain', 'text/csv', 'text/markdown',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }

    # File size limits (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20 MB

    def __init__(self, upload_folder: str):
        """
        Initialize file service.

        Args:
            upload_folder: Base directory for file uploads
        """
        # Convert to absolute path to ensure consistency
        self.upload_folder = Path(upload_folder).resolve()
        self.upload_folder.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for different file types
        self.images_folder = self.upload_folder / 'images'
        self.documents_folder = self.upload_folder / 'documents'
        self.images_folder.mkdir(exist_ok=True)
        self.documents_folder.mkdir(exist_ok=True)

    def validate_file(self, file: FileStorage) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file.

        Args:
            file: Uploaded file object

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file or not file.filename:
            return False, "No file provided"

        # Check file extension
        filename = secure_filename(file.filename)
        file_ext = Path(filename).suffix.lower()

        if file_ext not in self.ALLOWED_EXTENSIONS:
            allowed = ', '.join(sorted(self.ALLOWED_EXTENSIONS))
            return False, f"File type not allowed. Allowed types: {allowed}"

        # Check MIME type
        mime_type = file.content_type
        if mime_type not in self.ALLOWED_MIME_TYPES:
            return False, f"MIME type '{mime_type}' not allowed"

        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer

        if file_ext in self.ALLOWED_IMAGE_EXTENSIONS:
            if file_size > self.MAX_IMAGE_SIZE:
                max_mb = self.MAX_IMAGE_SIZE / (1024 * 1024)
                return False, f"Image file too large. Maximum size: {max_mb} MB"
        else:
            if file_size > self.MAX_DOCUMENT_SIZE:
                max_mb = self.MAX_DOCUMENT_SIZE / (1024 * 1024)
                return False, f"Document file too large. Maximum size: {max_mb} MB"

        # Images are validated by MIME type and extension
        # Additional validation could be done with PIL/Pillow if needed
        return True, None

    def save_file(self, file: FileStorage) -> Tuple[Optional[dict], Optional[str]]:
        """
        Save uploaded file securely.

        Args:
            file: Uploaded file object

        Returns:
            Tuple of (file_info_dict, error_message)
            file_info_dict contains: stored_filename, file_path, mime_type, file_size, file_type
        """
        # Validate file
        is_valid, error_msg = self.validate_file(file)
        if not is_valid:
            return None, error_msg

        try:
            # Get file info
            original_filename = secure_filename(file.filename)
            file_ext = Path(original_filename).suffix.lower()
            mime_type = file.content_type

            # Generate unique filename
            unique_id = str(uuid.uuid4())
            stored_filename = f"{unique_id}{file_ext}"

            # Determine file type and storage location
            if file_ext in self.ALLOWED_IMAGE_EXTENSIONS:
                file_type = 'image'
                storage_folder = self.images_folder
                relative_path = f'images/{stored_filename}'
            else:
                file_type = 'document'
                storage_folder = self.documents_folder
                relative_path = f'documents/{stored_filename}'

            # Save file
            file_path = storage_folder / stored_filename
            file.save(str(file_path))

            # Get file size
            file_size = file_path.stat().st_size

            return {
                'original_filename': original_filename,
                'stored_filename': stored_filename,
                'file_path': relative_path,
                'mime_type': mime_type,
                'file_size': file_size,
                'file_type': file_type
            }, None

        except Exception as e:
            return None, f"Error saving file: {str(e)}"

    def get_file_path(self, relative_path: str) -> Optional[Path]:
        """
        Get absolute file path from relative path.

        Args:
            relative_path: Relative path from uploads directory

        Returns:
            Absolute Path object or None if file doesn't exist
        """
        file_path = self.upload_folder / relative_path

        if file_path.exists() and file_path.is_file():
            return file_path

        return None

    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file.

        Args:
            relative_path: Relative path from uploads directory

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            file_path = self.get_file_path(relative_path)
            if file_path:
                file_path.unlink()
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted string (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def get_mime_type(self, filename: str) -> str:
        """
        Get MIME type for a filename.

        Args:
            filename: File name

        Returns:
            MIME type string
        """
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'
