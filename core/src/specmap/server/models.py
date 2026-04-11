"""Pydantic response models matching web/src/api/types.ts."""

from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    github_id: int
    login: str
    name: str
    avatar_url: str
    created_at: str
    updated_at: str


class RepositoryResponse(BaseModel):
    id: int
    github_id: int
    owner: str
    name: str
    full_name: str
    private: bool
    created_at: str
    updated_at: str


class PullRequestResponse(BaseModel):
    id: int
    repository_id: int
    number: int
    title: str
    state: str
    head_branch: str
    base_branch: str
    head_sha: str
    author_login: str
    created_at: str
    updated_at: str


class PullFileResponse(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str


class SpecRefResponse(BaseModel):
    id: int
    spec_file: str
    heading: str
    start_line: int
    excerpt: str


class AnnotationResponse(BaseModel):
    id: str
    file: str
    start_line: int
    end_line: int
    description: str
    refs: list[SpecRefResponse]
    created_at: str


class SpecmapFileResponse(BaseModel):
    version: int
    branch: str
    base_branch: str
    head_sha: str
    updated_at: str
    updated_by: str
    annotations: list[AnnotationResponse]
    ignore_patterns: list[str]


class SpecContentResponse(BaseModel):
    path: str
    content: str
