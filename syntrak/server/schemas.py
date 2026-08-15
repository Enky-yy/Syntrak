"""Pydantic schemas for the Syntrak Web API server."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# Authentication Schemas
class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="Google ID Token credential string from GIS")


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


# Conversation & Message Schemas
class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: Optional[str] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    user_id: str
    title: str
    mode: str = "chat"
    message_count: int = 0
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: str
    user_id: str
    title: str
    mode: str = "chat"
    created_at: str
    updated_at: str
    messages: List[MessageResponse] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Chat"
    mode: Optional[str] = "chat"



class UpdateConversationRequest(BaseModel):
    title: str


# Chat & Agent Schemas
class ChatRequest(BaseModel):
    query: str = Field(..., description="User prompt or instruction")
    custom_instructions: Optional[str] = None
    conversation_id: Optional[str] = None
    mode: str = Field(default="chat", description="'chat' (ChatGPT mode) or 'agent' (Repo Agent mode)")
    repo_authorized: bool = Field(default=False, description="Whether access to repository is authorized")


class RepoInfoResponse(BaseModel):
    workspace_root: str
    repo_name: str
    git_remote: Optional[str] = None
    branch: Optional[str] = None
    is_git_repo: bool = True


class AuthorizeRepoRequest(BaseModel):
    grant: bool = True
    github_token: Optional[str] = None


class ConnectGithubRepoRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL (e.g. 'https://github.com/user/repo') or 'owner/repo'")
    github_token: Optional[str] = Field(default=None, description="GitHub Personal Access Token (PAT)")
    branch: Optional[str] = Field(default="main", description="Target Git branch")



class ConnectGithubRepoResponse(BaseModel):
    status: str
    workspace_root: str
    repo_name: str
    git_remote: Optional[str] = None
    branch: Optional[str] = None
    message: str



class SwitchModelRequest(BaseModel):
    model: str = Field(..., description="New model name (e.g. ollama/qwen2.5-coder:32b)")
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    google_client_id: Optional[str] = None


class SessionInfoResponse(BaseModel):
    model: str
    api_base: Optional[str]
    workspace_root: Optional[str] = None
    has_connected_repo: bool = False
    connected_repo_name: Optional[str] = None
    git_status: str = "No repository connected"
    max_steps: int
    google_client_id: Optional[str] = None
    user: Optional[UserResponse] = None



class ReviewRequest(BaseModel):
    staged_only: bool = False
    target_branch: Optional[str] = None

