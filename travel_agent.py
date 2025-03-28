import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from typing import Optional, Literal, Union
from typing_extensions import Annotated, TypedDict

# import sys
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

# Load api key from .env file
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize gpt-4o-mini model
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=500,
    timeout=None,
    max_retries=2,
    openai_api_key=openai_api_key
    )

class UserIntent(TypedDict):
    """Intent of the user showing which action to take next about planning their trip."""

    intent: Annotated[Literal["flight", "car", "hotel"], ..., "Whether the user wants to proceed with flight booking, car rental, or hotel reservation."]

class ChatResponse(TypedDict):
    """A normal conversational response to the user's input."""

    response: Annotated[str, ..., "A normal assistant response to continue the conversation with the user."]

class TravelOutput(TypedDict):
    """Output of the travel assistant to the user input as a normal response or a specific intent."""

    travel_output: Annotated[Union[ChatResponse, UserIntent], ..., "Output of the travel assistant to the user input as a normal response or a specific intent."]


structured_llm = llm.with_structured_output(TravelOutput)


system_message = """You are a travel assistant at the entry point of a system that is capable of helping users with their flight bookings, car rentals and hotel reservations. Your main responsibility is to understand the user's intent and guide them to the appropriate part of the system, where further assistance on the specific needs of the user will be provided. You should keep a normal, human-like conversation until you understand the user's intent. Once the user's intent is clear and you're confident about guiding them to the right part of the system, you should output a structured response that is one of the 3 string literals:
1. "flight": If the user wants to proceed with flight booking.
2. "car": If the user wants to proceed with car rental.
3. "hotel": If the user wants to proceed with hotel reservation.

Besides your main responsibility, you should also follow these guidelines:
- Keep the conversation in a natural, human-like manner and be polite.
- Keep your answers as concise and to the point as possible.
- If the user asks/tells you anything about another/off-topic subject that is irrelevant to their trip or travel plans, state that you can only help with travel plans (flight booking, car rental and hotel reservation) and turn the conversation back to this topic.
- Assume the users are Turkish. So please give your conversational responses in Turkish.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_message), 
    ("placeholder", "{messages}")
    ])

travel_llm = prompt | structured_llm




if __name__ == "__main__":

    pass
