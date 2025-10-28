from asksageclient import AskSageClient
from dotenv import load_dotenv
import os
import sys


def main():
    load_dotenv()
    EMAIL = os.environ.get("EMAIL")
    API_KEY = os.environ.get("API_KEY")

    args = []
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            args.append(arg)

    if not args:
        print("Ask Sage AI\n")
        print('Usage: python main.py "your prompt here"\n')
        print("NO CUI\n")
        sys.exit(1)

    user_prompt = " ".join(args)

    client = AskSageClient(EMAIL, API_KEY)

    response = client.query(message=user_prompt)

    print(response)

if __name__ == "__main__":
    main()