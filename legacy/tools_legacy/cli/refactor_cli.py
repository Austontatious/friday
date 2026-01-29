import argparse
import json
from agents.refactor import refactor_code

def main():
    parser = argparse.ArgumentParser(description="FRIDAY Refactor CLI")
    parser.add_argument("filepath", help="Path to the source code file to refactor")
    parser.add_argument("--language", default="python", help="Programming language of the code")
    parser.add_argument("--style", default="best_practices", help="Refactor style (e.g. readability, performance)")
    parser.add_argument("--output", help="Optional file to write the refactored code to")

    args = parser.parse_args()

    try:
        with open(args.filepath, "r") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {args.filepath}")
        return

    result = refactor_code(code, language=args.language, filename=args.filepath, style=args.style)

    print("\n=== Refactored Code ===\n")
    print(result["refactored_code"])
    print("\n=== Explanation ===\n")
    print(result["explanation"])
    print("\n=== Diff Summary ===\n")
    print(result["diff_summary"])
    print("\n=== Test Result ===\n")
    print(json.dumps(result["test_result"], indent=2))

    if args.output:
        try:
            with open(args.output, "w") as out_file:
                out_file.write(result["refactored_code"])
            print(f"\nRefactored code saved to {args.output}")
        except Exception as e:
            print(f"Failed to write output: {e}")

if __name__ == "__main__":
    main()
