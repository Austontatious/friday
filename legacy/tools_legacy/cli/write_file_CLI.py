import argparse
from friday_code_tools import FridayCodeTools
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="FRIDAY File Writer CLI")
    parser.add_argument("filepath", help="Path (relative to base) to the file to write")
    parser.add_argument("--content", required=True, help="Content to write to the file")
    parser.add_argument("--base", default="./", help="Base directory for operation")
    parser.add_argument("--allow", nargs="*", default=[], help="List of writable relative paths")

    args = parser.parse_args()

    writer = FridayCodeTools(base_path=args.base, writable_paths=args.allow)

    try:
        writer.write_file(args.filepath, args.content)
        print(f"\n✅ File written successfully: {Path(args.base) / args.filepath}")
    except PermissionError as pe:
        print(f"\n❌ Permission denied: {pe}")
    except Exception as e:
        print(f"\n❌ Failed to write file: {e}")

if __name__ == "__main__":
    main()

