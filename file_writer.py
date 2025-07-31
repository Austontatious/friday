import os

def write_file(path: str, content: str, overwrite: bool = False) -> dict:
    """
    Writes content to a file. Creates parent folders if needed.
    Will not overwrite existing file unless explicitly allowed.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path) and not overwrite:
        return {
            "status": "error",
            "message": f"File already exists at {path}. Use --overwrite to force.",
            "path": path
        }

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "status": "success",
            "message": "File written successfully.",
            "path": path
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "path": path
        }
