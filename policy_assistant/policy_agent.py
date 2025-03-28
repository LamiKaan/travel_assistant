import os
# import sys
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from typing import Optional
from typing_extensions import Annotated, TypedDict

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

class PolicyReport(TypedDict):
    """Result of checking user-provided flight information against company policy."""

    complies: Annotated[bool, ..., "Whether the flight information complies with the company policy (True), or violates it (False)."]
    details: Annotated[Optional[str], None, "Further explanation (strictly in Turkish) on the exact aspect(s) of the company policy that the flight information violates."]

structured_llm = llm.with_structured_output(PolicyReport)

system_message = """You are a policy checking assistant. Your sole responsibility is to check if the flight information provided by the user complies with the company policy, or if it violates any of the policy rules.

The current policy of the company comprises of 2 rules, which are as follows:
1. The price of the flight must be less than or equal to 2000 TL (Turkish Lira). Any flight with a price exceeding this limit violates the policy and is not available for purchase.
2. The class of the flight must be "Economy". Any flight with a class other than "Economy" (e.g. "Business") violates the policy and is not available for purchase.

The user will provide the flight information in a python dictionary format, below is an examplary user input:
{{"airline": "THY", "departure_time": "05:30", "arrival_time": "07:15", "duration": "1h 45m", "class": "Business", "price": 5000, "flight_code": "TK802"}}
You can safely assume that the currency is Turkish Lira (TL) for all prices.

You should check the flight information against the company policy and provide a structured output that is also in a python dictionary format. The output should contain 2 fields:
1. "complies": A boolean value indicating whether the flight information complies with the company policy (True), or violates it (False).
2. "details": A string value providing further explanation on the exact aspect(s) of the company policy that the flight information violates. If the flight information complies with the policy, this field should be None. The explanation should be strictly in Turkish.

Here are some examples of user inputs and the expected outputs:

# Example 1
user_input: {{"airline": "THY", "departure_time": "05:30", "arrival_time": "07:15", "duration": "1h 45m", "class": "Business", "price": 5000, "flight_code": "TK802"}}
assistant_output: {{"complies": False, "details": "- 2000 TL'den pahali ucuslar secilemez, izin verilen en yuksek fiyat 2000 TL'dir.\n- 'Business' class ucuslar secilemez, sadece 'Economy' class ucuslar secilebilir."}}

# Example 2
user_input: {{"airline": "THY", "departure_time": "09:00", "arrival_time": "10:20", "duration": "1h 20m", "class": "Economy", "price": 1500, "flight_code": "TK801"}}
assistant_output: {{"complies": True, "details": None}}

# Example 3
user_input: {{"airline": "Pegasus", "departure_time": "16:45", "arrival_time": "18:20", "duration": "1h 35m", "class": "Economy", "price": 2000, "flight_code": "PC346"}}
assistant_output: {{"complies": True, "details": None}}

# Example 4
user_input: {{"airline": "Pegasus", "departure_time": "09:45", "arrival_time": "10:55", "duration": "1h 10m", "class": "Business", "price": 1800, "flight_code": "PC969"}}
assistant_output: {{"complies": False, "details": "'Business' class ucuslar secilemez, sadece 'Economy' class ucuslar secilebilir."}}

# Example 5
user_input: {{"airline": "Pegasus", "departure_time": "11:00", "arrival_time": "12:45", "duration": "1h 45m", "class": "Economy", "price": 2400, "flight_code": "PC970"}}
assistant_output: {{"complies": False, "details": "- 2000 TL'den pahali ucuslar secilemez, izin verilen en yuksek fiyat 2000 TL'dir."}}

# Example 6
user_input: {{"airline": "AJet", "departure_time": "18:15", "arrival_time": "19:45", "duration": "1h 30m", "class": "Economy", "price": 1000, "flight_code": "AJ255"}}
assistant_output: {{"complies": True, "details": None}}

# Example 7
user_input: {{"airline": "AJet", "departure_time": "18:15", "arrival_time": "19:45", "duration": "1h 30m", "class": "Business", "price": 2001, "flight_code": "AJ255"}}
assistant_output: {{"complies": False, "details": "- 2000 TL'den pahali ucuslar secilemez, izin verilen en yuksek fiyat 2000 TL'dir.\n- 'Business' class ucuslar secilemez, sadece 'Economy' class ucuslar secilebilir."}}
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_message), 
    ("human", "{input}")
    ])

policy_llm = prompt | structured_llm




if __name__ == "__main__":

    output = {"depart_flights": [{"airline": "SunExpress", "departure_time": "09:30", "arrival_time": "10:45", "duration": "1h 15m", "class": "Economy", "price": 2500, "flight_code": "SE328"}, {"airline": "THY", "departure_time": "16:30", "arrival_time": "17:45", "duration": "1h 15m", "class": "Economy", "price": 2000, "flight_code": "TK822"}, {"airline": "Pegasus", "departure_time": "22:15", "arrival_time": "23:45", "duration": "1h 30m", "class": "Business", "price": 5000, "flight_code": "PC519"}], "return_flights": [{"airline": "AJet", "departure_time": "02:45", "arrival_time": "04:30", "duration": "1h 45m", "class": "Economy", "price": 2000, "flight_code": "AJ144"}, {"airline": "SunExpress", "departure_time": "07:30", "arrival_time": "09:00", "duration": "1h 30m", "class": "Economy", "price": 2000, "flight_code": "SE827"}, {"airline": "THY", "departure_time": "11:00", "arrival_time": "12:15", "duration": "1h 15m", "class": "Business", "price": 4000, "flight_code": "TK979"}]}

    examples = [output["depart_flights"][0], output["depart_flights"][1], output["depart_flights"][2], output["return_flights"][0], output["return_flights"][1], output["return_flights"][2]]

    print("\n---------------------------------------\n")

    for example in examples:
        policy_result = policy_llm.invoke({"input":example})
        print(f"User input:\n{example}\n\nPolicy result:\n{policy_result}\n\nPolicy result type:\n{type(policy_result)}\n\nPolicy result details:\n{(policy_result["details"])}\n\n---------------------------------------\n\n")
