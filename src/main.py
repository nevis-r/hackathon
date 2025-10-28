from asksageclient import AskSageClient
from dotenv import load_dotenv
import os
import sys


def main():
    load_dotenv()
    EMAIL = os.environ.get("EMAIL")
    API_KEY = os.environ.get("API_KEY")

    # Get user prompt from CLI
    args = []
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            args.append(arg)

    if not args:
        print("Ask Sage AI\n")
        print('Usage: python main.py "your prompt here"\n')
        print("NO CUI\n")
        sys.exit(1)

    # Load system prompt from a file
    system_prompt_file = "system_prompt.txt"
    try:
        with open(system_prompt_file, "r") as file:
            system_prompt = file.read().strip()
    except FileNotFoundError:
        print(f"Error: Background file '{system_prompt_file}' not found.")
        sys.exit(1)

    user_prompt = " ".join(args)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    client = AskSageClient(EMAIL, API_KEY)

    response = client.query(message=full_prompt)

    print(response)

if __name__ == "__main__":
    main()