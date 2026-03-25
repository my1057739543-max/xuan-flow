import base64
import mimetypes
from pathlib import Path
from langchain_core.tools import tool

@tool("inspect_image_metadata", parse_docstring=True)
def inspect_image_metadata(
    image_path: str,
) -> str:
    """Inspect an image file to retrieve its format, resolution metadata, and properties.

    Use this tool when you need to view or process an image file in the workspace.
    Note: Due to text-only LLM constraints, this tool returns metadata rather than true visual inference.

    Args:
        image_path: Absolute path to the image file in the workspace.
    """
    actual_path = Path(image_path)

    if not actual_path.is_absolute():
        return f"Error: Path must be absolute, got: {image_path}"

    if not actual_path.exists():
        return f"Error: Image file not found: {image_path}"

    if not actual_path.is_file():
        return f"Error: Path is not a file: {image_path}"

    valid_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
    if actual_path.suffix.lower() not in valid_extensions:
        return f"Error: Unsupported image format: {actual_path.suffix}. Supported: {', '.join(valid_extensions)}"

    file_size_kb = actual_path.stat().st_size / 1024
    mime_type, _ = mimetypes.guess_type(str(actual_path))
    
    return (
        f"Image Inspection Results for {actual_path.name}:\n"
        f"- Format: {mime_type}\n"
        f"- File Size: {file_size_kb:.2f} KB\n"
        f"- Notice: Full vision capability is deferred to the multimodal backend. "
        f"For now, the image exists and is ready for external processing or UI presentation."
    )
