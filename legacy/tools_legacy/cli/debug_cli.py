import argparse
import json
from agents.debug import debug_code

def main():
    parser = argparse.ArgumentParser(description="FRIDAY Debug CLI")
    parser.add_argument("filepath", help="Path to the source code file to debug")
    parser.add_argument("--language", default="python", help="Programming language of the code")
    parser.add_argument("--error", default="", help="Optional error message or log")
    parser.add_argument("--output", help="Optional file to write the fixed code to")

    args = parser.parse_args()

    try:
        with open(args.filepath, "r") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {args.filepath}")
        return

    result = debug_code(code, language=args.language, error_message=args.error, filename=args.filepath)

    print("\n=== Fixed Code ===\n")
    print(result["fixed_code"])
    print("\n=== Explanation ===\n")
    print(result["explanation"])
    print("\n=== Error Summary ===\n")
    print(result["error_summary"])
    print("\n=== Test Result ===\n")
    print(json.dumps(result["test_result"], indent=2))

    if args.output:
        try:
            with open(args.output, "w") as out_file:
                out_file.write(result["fixed_code"])
            print(f"\nFixed code saved to {args.output}")
        except Exception as e:
            print(f"Failed to write output: {e}")

if __name__ == "__main__":
    main()
