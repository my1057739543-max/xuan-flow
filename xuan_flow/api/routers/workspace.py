"""Workspace endpoints for the Gateway API."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)
router = APIRouter()

WORKSPACE_DIR = Path.cwd() / ".xuan-flow" / "workspace"

def _get_safe_path(filename: str) -> Path | None:
    try:
        clean_name = os.path.basename(filename)
        if not clean_name:
            return None
        safe_path = (WORKSPACE_DIR / clean_name).resolve()
        if not str(safe_path).startswith(str(WORKSPACE_DIR.resolve())):
            return None
        return safe_path
    except Exception:
        return None

@router.get("/files")
async def list_workspace_files():
    """List all files in the agent's workspace."""
    try:
        if not WORKSPACE_DIR.exists():
            return {"status": "success", "files": []}
            
        files = []
        for file_path in WORKSPACE_DIR.iterdir():
            if file_path.is_file() and not file_path.name.startswith("."):
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified_at": stat.st_mtime
                })
                
        # Sort by modified_at descending (newest first)
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        return {"status": "success", "files": files}
        
    except Exception as e:
        logger.error(f"Failed to list workspace files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{filename}")
async def get_workspace_file(filename: str):
    """Get the content of a specific workspace file."""
    safe_path = _get_safe_path(filename)
    if not safe_path or not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        content = safe_path.read_text(encoding="utf-8")
        return {"status": "success", "name": filename, "content": content}
    except Exception as e:
        logger.error(f"Failed to read workspace file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{filename}")
async def delete_workspace_file(filename: str):
    """Delete a specific workspace file."""
    safe_path = _get_safe_path(filename)
    if not safe_path or not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        safe_path.unlink()
        return {"status": "success", "detail": f"File {filename} deleted"}
    except Exception as e:
        logger.error(f"Failed to delete workspace file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
