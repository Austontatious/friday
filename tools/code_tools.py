import os
from pathlib import Path
from typing import List, Optional
from ..utils.chunking import chunk_code
from friday.memory import MemoryManager

SUPPORTED_EXTENSIONS = [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json"]


class FridayCodeTools:
    def __init__(self, base_path: str = "./", writable_paths: Optional[List[str]] = None, project_name: str = "default_project"):
        self.base_path = Path(base_path).resolve()
        self.allowed_writes = {
            str((self.base_path / p).resolve()) for p in (writable_paths or [])
        }
        self.project_name = project_name
        self.memory = MemoryManager()

    def list_files(self, extensions: Optional[List[str]] = None) -> str:
        if extensions is None:
            extensions = SUPPORTED_EXTENSIONS
        files = [
            str(f.relative_to(self.base_path))
            for f in self.base_path.rglob("*")
            if f.suffix in extensions and f.is_file()
        ]
        return "\n".join(files)  # ✅ Return human-readable format

    def read_file(self, relative_path: str) -> str:
        file_path = (self.base_path / relative_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"{relative_path} not found")
        if not file_path.is_file():
            raise ValueError(f"{relative_path} is not a file")
        return file_path.read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> None:
        file_path = (self.base_path / relative_path).resolve()
        if str(file_path) not in self.allowed_writes:
            raise PermissionError(f"Write access denied: {relative_path}")
        file_path.write_text(content, encoding="utf-8")

    def scan_codebase(self) -> str:
        file_count = 0
        chunk_count = 0

        for root, _, files in os.walk(self.base_path):
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        code = f.read()
                    chunks = chunk_code(code, filepath)
                    for chunk in chunks:
                        self.memory.store_interaction({
                            "source": filepath,
                            "project": self.project_name,
                            "chunk": chunk
                        })
                        chunk_count += 1
                    file_count += 1
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")

        return (
            f"Scan complete for project '{self.project_name}':\n"
            f"- Files scanned: {file_count}\n"
            f"- Chunks saved: {chunk_count}"
        )

