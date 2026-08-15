"""SQLAlchemy database persistence layer for Syntrak Web Server."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, Generator, List, Optional, Union
import uuid

from sqlalchemy import (
    Engine,
    ForeignKey,
    Index,
    String,
    Text,
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


def get_db_path() -> Path:
    """Get path to database from environment variables or default to ~/.syntrak/syntrak.db."""
    db_env = (
        os.getenv("DATABASE_URL")
        or os.getenv("SQL_DATABASE_URL")
        or os.getenv("DATABASE_PATH")
        or os.getenv("SQL_DATABASE_PATH")
        or os.getenv("SYNTRAK_DATABASE_PATH")
    )
    if db_env:
        # Strip sqlite URI prefix if present
        if db_env.startswith("sqlite:///"):
            db_env = db_env[len("sqlite:///"):]
        elif db_env.startswith("sqlite://"):
            db_env = db_env[len("sqlite://"):]
        p = Path(db_env).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    db_dir = Path.home() / ".syntrak"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "syntrak.db"


def get_db_url(
    db_path: Optional[Union[str, Path]] = None,
    db_url: Optional[str] = None,
) -> str:
    """Get SQLAlchemy database connection URL."""
    url: Optional[str] = None
    if db_url:
        url = db_url
    elif db_path is not None:
        p = Path(db_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{p}"
    else:
        db_env = (
            os.getenv("DATABASE_URL")
            or os.getenv("SQL_DATABASE_URL")
            or os.getenv("DATABASE_PATH")
            or os.getenv("SQL_DATABASE_PATH")
            or os.getenv("SYNTRAK_DATABASE_PATH")
        )
        if db_env:
            if "://" in db_env:
                url = db_env
            else:
                p = Path(db_env).expanduser().resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                url = f"sqlite:///{p}"
        else:
            path = get_db_path().resolve()
            url = f"sqlite:///{path}"

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


# Enable SQLite foreign key cascade support
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base for Syntrak models."""
    pass


class UserModel(Base):
    """Registered or guest user entity."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    picture: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.now(timezone.utc).isoformat()
    )

    conversations: Mapped[List["ConversationModel"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "created_at": self.created_at,
        }


class ConversationModel(Base):
    """Chat conversation thread entity."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False, default="New Chat")
    created_at: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        index=True
    )

    user: Mapped["UserModel"] = relationship(back_populates="conversations")
    messages: Mapped[List["MessageModel"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MessageModel.created_at",
    )

    __table_args__ = (
        Index("idx_conversations_user", "user_id", "updated_at"),
    )

    def to_dict(self, message_count: int = 0) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": message_count,
        }


class MessageModel(Base):
    """Individual message in a conversation thread."""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    events_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        index=True
    )

    conversation: Mapped["ConversationModel"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("idx_messages_conv", "conversation_id", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        events = []
        if self.events_json:
            try:
                events = json.loads(self.events_json)
            except Exception:
                events = []
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "events": events,
            "created_at": self.created_at,
        }


# Aliases for convenience
User = UserModel
Conversation = ConversationModel
Message = MessageModel


class Database:
    """Thread-safe SQLAlchemy database manager for chat history and users."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        db_url: Optional[str] = None,
    ):
        target_url = get_db_url(db_path=db_path, db_url=db_url)
        self.db_url = target_url
        try:
            self._setup_engine(self.db_url)
            self.init_db()
        except Exception as e:
            # Fallback to local SQLite if remote DB driver is missing or connection fails
            if not self.db_url.startswith("sqlite"):
                fallback_path = get_db_path().resolve()
                fallback_url = f"sqlite:///{fallback_path}"
                print(f"Warning: Failed to connect to database at {self.db_url} ({e}). Falling back to local SQLite at {fallback_url}")
                self.db_url = fallback_url
                self._setup_engine(self.db_url)
                self.init_db()
            else:
                raise

    def _setup_engine(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        self.session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def init_db(self):
        """Create database tables if they do not exist."""
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Context manager providing a transactional SQLAlchemy Session."""
        session: Session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # User operations
    def upsert_user(
        self,
        user_id: str,
        email: str,
        name: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert or update user profile."""
        with self.get_session() as session:
            user = session.get(UserModel, user_id)
            if user:
                user.email = email
                if name is not None:
                    user.name = name
                if picture is not None:
                    user.picture = picture
            else:
                user = UserModel(
                    id=user_id,
                    email=email,
                    name=name,
                    picture=picture,
                )
                session.add(user)
            session.flush()
            return user.to_dict()

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user record by ID."""
        with self.get_session() as session:
            user = session.get(UserModel, user_id)
            return user.to_dict() if user else None

    # Conversation operations
    def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new conversation thread for user."""
        # Ensure user exists (auto-create guest if needed)
        self.upsert_user(
            user_id=user_id,
            email=f"{user_id}@local.user",
            name="Guest Developer",
        )

        conv_id = conversation_id or str(uuid.uuid4())
        conv_title = title or "New Chat"
        now = datetime.now(timezone.utc).isoformat()

        with self.get_session() as session:
            conv = ConversationModel(
                id=conv_id,
                user_id=user_id,
                title=conv_title,
                created_at=now,
                updated_at=now,
            )
            session.add(conv)
            session.flush()
            return conv.to_dict(message_count=0)

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """List all conversation threads with message counts for a user."""
        with self.get_session() as session:
            stmt = (
                select(
                    ConversationModel,
                    func.count(MessageModel.id).label("message_count"),
                )
                .outerjoin(MessageModel, ConversationModel.id == MessageModel.conversation_id)
                .where(ConversationModel.user_id == user_id)
                .group_by(ConversationModel.id)
                .order_by(ConversationModel.updated_at.desc())
            )
            results = []
            for conv, msg_count in session.execute(stmt):
                results.append(conv.to_dict(message_count=msg_count))
            return results

    def get_conversation(
        self,
        conversation_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a specific conversation thread."""
        with self.get_session() as session:
            stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
            if user_id:
                stmt = stmt.where(ConversationModel.user_id == user_id)
            conv = session.scalar(stmt)
            return conv.to_dict() if conv else None

    def update_conversation_title(
        self,
        conversation_id: str,
        title: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """Update the title and updated_at timestamp of a conversation."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_session() as session:
            stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
            if user_id:
                stmt = stmt.where(ConversationModel.user_id == user_id)
            conv = session.scalar(stmt)
            if conv:
                conv.title = title
                conv.updated_at = now
                return True
            return False

    def touch_conversation(self, conversation_id: str):
        """Update the conversation's updated_at timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_session() as session:
            conv = session.get(ConversationModel, conversation_id)
            if conv:
                conv.updated_at = now

    def delete_conversation(
        self,
        conversation_id: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """Delete a conversation and its messages."""
        with self.get_session() as session:
            stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
            if user_id:
                stmt = stmt.where(ConversationModel.user_id == user_id)
            conv = session.scalar(stmt)
            if conv:
                session.delete(conv)
                return True
            return False

    # Message operations
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: Optional[str] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a new chat message and refresh conversation updated_at."""
        msg_id = message_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        events_json = json.dumps(events) if events else None

        with self.get_session() as session:
            msg = MessageModel(
                id=msg_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                events_json=events_json,
                created_at=now,
            )
            session.add(msg)
            # Update parent conversation updated_at
            conv = session.get(ConversationModel, conversation_id)
            if conv:
                conv.updated_at = now
            session.flush()
            return msg.to_dict()

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieve all messages for a conversation in chronological order."""
        with self.get_session() as session:
            stmt = (
                select(MessageModel)
                .where(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.created_at.asc())
            )
            messages = session.scalars(stmt).all()
            return [msg.to_dict() for msg in messages]


# Global singleton instance
default_db = Database()
