from fastapi import APIRouter, Query, Body
from code_reader import CodeReader

code_router = APIRouter()
reader = CodeReader(
    base_path="/mnt/ai-lab/friday/",
    writable_paths=["persona.txt"]
)

@code_router.get("/friday/code/files")
def list_files():
    """List all readable source code files."""
    return {"files": reader.list_files()}

@code_router.get("/friday/code/read")
def read_file(path: str = Query(...)):
    """Read a specific source file."""
    return {"content": reader.read_file(path)}

@code_router.post("/friday/code/write")
def write_file(path: str = Query(...), content: str = Body(...)):
    """Write to an approved file like persona.txt."""
    reader.write_file(path, content)
    return {"status": "success", "path": path}

