import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment variables from .env
load_dotenv()

def test_llm():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return

    print(f"Using API Key: {api_key[:10]}...")
    
    try:
        llm = ChatOpenAI(
            model="nvidia/nemotron-3-nano-30b-a3b:free",
            temperature=0,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=api_key,
        )
        
        print("Sending request to OpenRouter...")
        response = llm.invoke("Who are you?'")
        print("\nResponse from LLM:")
        print(response.content)
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    test_llm()
