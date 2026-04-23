import sys
from backend.ai.main import process_document


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_ai.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]

    result = process_document(file_path)

    print(result)


if __name__ == "__main__":
    main()