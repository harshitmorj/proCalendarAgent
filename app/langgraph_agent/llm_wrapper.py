# llm_wrapper.py
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import List, Union
import os
from dotenv import load_dotenv

load_dotenv(override=True)

class LLMWrapper:
    def __init__(self):
        # Enable tracing with tags for better identification
        self.primary = ChatOpenAI(
            model="gpt-4.1-2025-04-14",
            temperature=0.5,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            tags=["calendar-agent", "openai", "primary-llm"]
        )
        self.fallback = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            temperature=0.5,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            tags=["calendar-agent", "google", "fallback-llm"]
        )

    def invoke(self, messages: List[Union[str, BaseMessage]]) -> str:
        """
        messages: list of LangChain HumanMessage/AIMessage or raw strings
        """
        lc_messages = []
        for msg in messages:
            if isinstance(msg, str):
                lc_messages.append(HumanMessage(content=msg))
            else:
                lc_messages.append(msg)

        # Try OpenAI with tracing
        try:
            response = self.primary.invoke(
                lc_messages,
                config={"tags": ["primary-attempt"], "metadata": {"node": "llm_primary"}}
            )
            return response.content
        except Exception as e:
            print(f"[LLMWrapper] OpenAI failed: {e}")
            try:
                response = self.fallback.invoke(
                    lc_messages,
                    config={"tags": ["fallback-attempt"], "metadata": {"node": "llm_fallback"}}
                )
                return response.content
            except Exception as fe:
                print(f"[LLMWrapper] Gemini fallback failed: {fe}")
                return "Sorry, both LLMs failed to generate a response."
