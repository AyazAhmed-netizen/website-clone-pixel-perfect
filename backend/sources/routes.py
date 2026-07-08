"""
Sources API Routes

文件系统存储的 sources API，用于开源版本。
Sources 数据存储在 data/sources/ 目录下的 JSON 文件中。
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ============================================
# Router Setup
# ============================================

sources_router = APIRouter(prefix="/api/sources", tags=["sources"])

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data" / "sources"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================
# Models
# ============================================

class SourceMetadata(BaseModel):
    viewport: Optional[dict] = None
    extracted_at: Optional[str] = None
    theme: Optional[str] = "light"


class SavedSource(BaseModel):
    id: str
    source_url: str
    page_title: Optional[str] = None
    json_size: int = 0
    top_keys: List[str] = []
    metadata: SourceMetadata = SourceMetadata()
    created_at: str
    updated_at: str
    # Full data stored separately
    data: Optional[dict] = None


class CreateSourceRequest(BaseModel):
    source_url: str
    page_title: Optional[str] = None
    data: dict
    metadata: Optional[SourceMetadata] = None


class SourcesListResponse(BaseModel):
    success: bool
    sources: List[SavedSource]


class SourceResponse(BaseModel):
    success: bool
    source: SavedSource


# ============================================
# Helper Functions
# ============================================

def get_source_file_path(source_id: str) -> Path:
    """Get the file path for a source"""
    return DATA_DIR / f"{source_id}.json"


def load_source(source_id: str) -> Optional[SavedSource]:
    """Load a source from file"""
    file_path = get_source_file_path(source_id)
    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return SavedSource(**data)
    except Exception as e:
        print(f"Error loading source {source_id}: {e}")
        return None


def save_source(source: SavedSource) -> bool:
    """Save a source to file"""
    file_path = get_source_file_path(source.id)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(source.model_dump(), f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving source {source.id}: {e}")
        return False


def delete_source_file(source_id: str) -> bool:
    """Delete a source file"""
    file_path = get_source_file_path(source_id)

    try:
        if file_path.exists():
            file_path.unlink()
        return True
    except Exception as e:
        print(f"Error deleting source {source_id}: {e}")
        return False


def list_all_sources() -> List[SavedSource]:
    """List all sources (without full data)"""
    sources = []

    for file_path in DATA_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Remove full data for listing (to keep response small)
                data.pop("data", None)
                sources.append(SavedSource(**data))
        except Exception as e:
            print(f"Error loading source {file_path}: {e}")
            continue

    # Sort by created_at descending
    sources.sort(key=lambda s: s.created_at, reverse=True)
    return sources


# ============================================
# API Routes
# ============================================

@sources_router.get("", response_model=SourcesListResponse)
async def get_sources():
    """
    Get all saved sources (without full data).

    Returns a list of source metadata for display in the UI.
    """
    sources = list_all_sources()
    return SourcesListResponse(success=True, sources=sources)


@sources_router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str):
    """
    Get a single source with full data.

    Use this when the Agent needs to access the extracted data.
    """
    source = load_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return SourceResponse(success=True, source=source)


@sources_router.post("", response_model=SourceResponse)
async def create_source(request: CreateSourceRequest):
    """
    Create a new source.

    Called from the Extractor page to save extracted website data.
    """
    now = datetime.utcnow().isoformat() + "Z"
    source_id = str(uuid.uuid4())

    # Calculate data size and extract top keys
    data_str = json.dumps(request.data)
    json_size = len(data_str.encode("utf-8"))
    top_keys = list(request.data.keys())[:10]

    source = SavedSource(
        id=source_id,
        source_url=request.source_url,
        page_title=request.page_title,
        json_size=json_size,
        top_keys=top_keys,
        metadata=request.metadata or SourceMetadata(extracted_at=now),
        created_at=now,
        updated_at=now,
        data=request.data,
    )

    if not save_source(source):
        raise HTTPException(status_code=500, detail="Failed to save source")

    # Return without full data
    source.data = None
    return SourceResponse(success=True, source=source)


@sources_router.delete("/{source_id}")
async def delete_source(source_id: str):
    """
    Delete a source.
    """
    source = load_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if not delete_source_file(source_id):
        raise HTTPException(status_code=500, detail="Failed to delete source")

    return {"success": True, "message": "Source deleted"}
