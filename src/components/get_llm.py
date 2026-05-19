from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

api_key = os.getenv("GOOGLE_API_KEY")

def get_llm(
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.5,
) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        api_key=api_key,
        convert_system_message_to_human=True,  # thường cần cho system prompt
    )
