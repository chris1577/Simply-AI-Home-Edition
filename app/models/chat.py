from app import db
from datetime import datetime
import uuid


class Chat(db.Model):
    """Chat session model"""

    __tablename__ = 'chats'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    name = db.Column(db.String(255), nullable=False)

    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # Required - all chats must belong to a user

    # Chat settings
    model_provider = db.Column(db.String(50), default='gemini')  # 'gemini', 'openai', 'anthropic', 'lmstudio', 'ollama'
    model_name = db.Column(db.String(100), nullable=True)

    # Status
    is_deleted = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='chats')
    messages = db.relationship(
        'Message',
        back_populates='chat',
        cascade='all, delete-orphan',
        lazy='dynamic',
        order_by='Message.created_at'
    )

    def to_dict(self, include_messages=False):
        """Convert chat to dictionary"""
        data = {
            'id': self.id,
            'session_id': self.session_id,
            'name': self.name,
            'model_provider': self.model_provider,
            'model_name': self.model_name,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'message_count': self.messages.count()
        }

        if include_messages:
            data['messages'] = [msg.to_dict() for msg in self.messages.all()]

        return data

    def __repr__(self):
        return f'<Chat {self.name}>'


class Message(db.Model):
    """Chat message model"""

    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id'), nullable=False, index=True)

    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    distilled_content = db.Column(db.Text, nullable=True)  # Summarized version for context compression

    # Metadata
    tokens_used = db.Column(db.Integer, default=0)
    model_used = db.Column(db.String(100), nullable=True)

    # Token tracking
    input_tokens = db.Column(db.Integer, default=0)  # Tokens in user message / prompt
    output_tokens = db.Column(db.Integer, default=0)  # Tokens in assistant response
    tokens_estimated = db.Column(db.Boolean, default=False)  # True if tokens were estimated (local models)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    chat = db.relationship('Chat', back_populates='messages')
    attachments = db.relationship(
        'Attachment',
        back_populates='message',
        cascade='all, delete-orphan',
        lazy='joined'
    )

    def to_dict(self):
        """Convert message to dictionary"""
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'distilled_content': self.distilled_content,
            'tokens_used': self.tokens_used,
            'model_used': self.model_used,
            'input_tokens': self.input_tokens or 0,
            'output_tokens': self.output_tokens or 0,
            'tokens_estimated': self.tokens_estimated or False,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'attachments': [att.to_dict() for att in self.attachments] if self.attachments else []
        }

    def __repr__(self):
        return f'<Message {self.id} in Chat {self.chat_id}>'
