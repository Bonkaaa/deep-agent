import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI


def get_llm(
    provider: str = "google",
    model_name: str | None = None,
    temperature: float = 0.5,
):
    provider = provider.lower()
    if provider == "google" and os.getenv("ANTHROPIC_API_KEY"):
        provider = "anthropic"

    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name or "gemini-3.5-flash-lite",
            temperature=temperature,
            api_key=os.getenv("GOOGLE_API_KEY"),
            convert_system_message_to_human=True,
        )

    elif provider == "anthropic":
        return ChatAnthropic(
            model=model_name or "claude-opus-5",
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_api_url="https://agentrouter.org",
            default_headers={"User-Agent": "claude-cli/2.1.119 (external, cli)"}
        )

    elif provider == "openai":
        return ChatOpenAI(
            model=model_name or "gpt-5",
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    elif provider == "mistral":
        class WrappedChatMistralAI(ChatMistralAI):
            def __getattribute__(self, name):
                if name == "profile":
                    prof = super().__getattribute__("profile")
                    if isinstance(prof, property):
                        prof = prof.__get__(self, self.__class__)
                    if isinstance(prof, dict):
                        prof = dict(prof)
                        prof["structured_output"] = False
                    return prof
                return super().__getattribute__(name)

            def bind(self, *args, **kwargs):
                kwargs.pop("strict", None)
                return super().bind(*args, **kwargs)

            def bind_tools(self, *args, **kwargs):
                kwargs.pop("strict", None)
                return super().bind_tools(*args, **kwargs)

        return WrappedChatMistralAI(
            model=model_name or "mistral-medium-latest",
            temperature=temperature,
            api_key=os.getenv("MISTRAL_API_KEY"),
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")

if __name__ == "__main__":
    from langchain_core.messages import HumanMessage, SystemMessage
    llm = get_llm()
    response = llm.invoke([SystemMessage(content="You are a helpful assistant."), HumanMessage(content="Hello, how are you?")])
    print(response.content)