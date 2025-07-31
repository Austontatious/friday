import argparse
import json
from friday_code_tools import FridayCodeTools

def main():
    parser = argparse.ArgumentParser(description="FRIDAY Codebase Reader CLI")
    parser.add_argument("directory", help="Path to project directory")
    parser.add_argument("--project", default="default_project", help="Name to tag this codebase")

    args = parser.parse_args()

    tools = FridayCodeTools(base_path=args.directory, project_name=args.project)
    result = tools.scan_codebase()

    print("\n=== Codebase Scan Summary ===")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

