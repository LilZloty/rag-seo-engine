"""
Chat Models - Database models for conversational AI
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import uuid


class ChatSession(Base):
    """A chat conversation session"""
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=True)  # Auto-generated from first message
    user_id = Column(String, nullable=True)  # For future auth
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    context_data = Column(JSON, default=dict)  # Product IDs, filters, etc.
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """Individual chat message"""
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey('chat_sessions.id', ondelete='CASCADE'))
    role = Column(String(20))  # 'user', 'assistant', 'system', 'tool'
    content = Column(Text)
    
    # For tool/function calls
    tool_calls = Column(JSON, nullable=True)  # List of tool calls
    tool_results = Column(JSON, nullable=True)  # Results from tool execution
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    tokens_used = Column(Integer, nullable=True)
    model_used = Column(String(50), nullable=True)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")


class ChatToolLog(Base):
    """Log of tool executions for debugging"""
    __tablename__ = "chat_tool_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, ForeignKey('chat_messages.id'))
    tool_name = Column(String(50))
    tool_input = Column(JSON)
    tool_output = Column(JSON)
    execution_time_ms = Column(Integer)
    success = Column(Integer)  # 1 = success, 0 = failure
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
