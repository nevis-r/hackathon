from google import genai
from dotenv import load_dotenv
import os
import sys
from system_prompts import SYSTEM_PROMPT_1


def main():
    load_dotenv()
    MODEL = os.environ.get("MODEL")
    API_KEY = os.environ.get("API_KEY")

    # Get user prompt from CLI
    args = []
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            args.append(arg)

    if not args:
        print("Unofficial AF Award Writer AI\n")
        print('Usage: python main.py "your prompt here"\n')
        print("NO CUI\n")
        sys.exit(1)

    system_prompt = SYSTEM_PROMPT_1
    user_prompt = " ".join(args)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    client = genai.Client(api_key=API_KEY)
    
    response = client.models.generate_content(
    model=MODEL,
    contents=full_prompt,
    )

    print(response)

if __name__ == "__main__":
    main()