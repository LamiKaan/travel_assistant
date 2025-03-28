import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig

from typing import Annotated, Optional
from typing_extensions import TypedDict, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from flight_assistant.flight_agent import flight_prompt
from flight_assistant.flight_graph import FlightState, flight_graph
from flight_assistant.utils import pretty_print_object
from travel_agent import travel_llm


class TravelState(TypedDict):
    messages: Annotated[list, add_messages]
    travel_messages: Annotated[list, add_messages]
    intent: Optional[Literal["flight", "car", "hotel"]]
    flight_state: Optional[FlightState]
    initial: bool
    new: bool

def travel_node(state: TravelState) -> Command[Literal["flight_node", "car_node", "hotel_node", "travel_node", END]]:

    # If the intent is None (ongoing conversation with travel assistant)
    if state["intent"] is None:
        # Retrieve the last message from the state
        last_message = state["messages"][-1]

        # If the last message is a user message
        if last_message.type == "human":
            # # Add the user input to travel-specific history to keep travel_llm context separate from flight_graph's context
            input_travel_messages = state["travel_messages"] + [last_message]
    
            # Then invoke the travel llm with this meesage history
            output = travel_llm.invoke({"messages": input_travel_messages})
            # print(type(output))
            # print(output)
            # print(output["travel_output"])

            # Even tough I configured the travel_llm to give a structured output in the TravelOutput format, it sometimes gives a simple string response
            # In that case, I manually wrap the response in a TravelOutput structure to handle it in the same way in the rest of the code and avoid errors
            if "travel_output" not in output:
                output_response = output.get("response", output["response"])
                output = {"travel_output": {"response": output_response}}
            travel_output = output["travel_output"]

            # If the output includes the user intent
            if "intent" in travel_output:
                # Create a synthetic ai message that tells the user that they're being forwarded to the appropriate agent based on their intent
                intended_agent = {"flight": "ucus arama", "car": "arac kiralama", "hotel": "otel rezervasyonu"}[travel_output["intent"]]
                ai_response = AIMessage(content=f"Sizi {intended_agent} asistanina yonlendiriyorum.")
                travel_response = AIMessage(content=f"{output}")

                # Update the state
                return Command(update={"messages": [ai_response],"travel_messages": [last_message, travel_response], "intent": travel_output["intent"], "new": True}, goto="travel_node")

            # If the output is a chat response
            else:
                # Assert that the response is a chat response
                assert "response" in travel_output

                # Construct the response into an ai message
                ai_response = AIMessage(content=travel_output["response"])
                # print(ai_response)
                travel_response = AIMessage(content=f"{output}")
                
                # Update the state
                return Command(update={"messages": [ai_response], "travel_messages": [last_message, travel_response]}, goto=END)

        # If the last message is a system message
        elif last_message.type == "system":
            # Travel node can receive a system message from other nodes as an additional context or a directive
            # (e.g. car rental/hotel reservation is not available, flight booking completed etc.)
            # In that case, invoke the travel_llm to make it produce an appropriate ai message that conveys the situation to the user
            input_travel_messages = state["travel_messages"] + [last_message]
            output = travel_llm.invoke({"messages": input_travel_messages})
            travel_output = output["travel_output"]

            # We expect the output after a system message to be a chat response, not an intent decision
            assert "response" in travel_output
            ai_response = AIMessage(content=travel_output["response"])
            travel_response = AIMessage(content=f"{output}")

            # Update the state
            return Command(update={"messages": [ai_response], "travel_messages": [last_message, travel_response]}, goto=END)

        # If the last message is an ai message
        elif last_message.type == "ai":
            # Then the travel node should halt the pipeline (END --> until next user interaction)
            return Command(goto=END)
        
        # If the last message is a tool message
        else:
            # This should never happen as the travel node is not bound to any tool
            # Print current state and raise an exception
            print("\nUNEXPECTED TOOL MESSAGE IN TRAVEL NODE!\nSTATE DURING EXCEPTION:\n")
            pretty_print_object(state)
            raise Exception("Tool message type in travel node")

    # If the intent is "flight"
    elif state["intent"] == "flight":
        return Command(goto="flight_node")
    
    # If the intent is "car"
    elif state["intent"] == "car":
        return Command(goto="car_node")
    
    # If the intent is "hotel"
    else:
        return Command(goto="hotel_node")


def flight_node(state: TravelState, config: RunnableConfig) -> Command[Literal["travel_node", "flight_node", END]]:

    # If this is the initial entry to the flight node during the whole run of the travel graph
    if state["initial"]:
        # Then it should also be a new round of conversation with the flight assistant
        assert state["new"]

        # Define the initial state to initialize the flight graph with
        initial_state = {
            # Inject a user message in addition to the system prompt to trigger a greeting ai message from the flight assistant
            "messages": [SystemMessage(content=flight_prompt), HumanMessage(content="merhaba")],
            "latest_tool_call": None,
            "next_action": "flight_search",
            "retrieved_depart_flights": None,
            "retrieved_return_flights": None,
            "selected_depart_flight": None,
            "selected_return_flight": None,
            "escalation_message": None,
            "purchased_depart_ticket": None,
            "purchased_return_ticket": None,
            "flight_completed": False,
        }

        # Invoke the flight graph with the initial state
        flight_state = flight_graph.invoke(input=initial_state, config=config)

        # Get the last message from the flight state
        last_message = flight_state["messages"][-1]
        # We expect the last message to be an ai message that greets the user
        assert last_message.type == "ai"

        # Update the state and halt execution (END --> until next user interaction)
        return Command(update={"messages": [last_message], "flight_state": flight_state, "initial": False, "new": False}, goto=END)
    
    # If it's not the initial entry to the flight node, but a new round of conversation with the flight assistant
    elif state["initial"] == False and state["new"]:
        # Get the current flight state
        flight_state = state["flight_state"]

        # Create a new flight state with all fields reset to initial values except the message history, and again, inject a user message to trigger a greeting ai message from the flight assistant
        new_state = {
            "messages": flight_state["messages"] + [HumanMessage(content="Tekrardan merhaba.")],
            "latest_tool_call": None,
            "next_action": "flight_search",
            "retrieved_depart_flights": None,
            "retrieved_return_flights": None,
            "selected_depart_flight": None,
            "selected_return_flight": None,
            "escalation_message": None,
            "purchased_depart_ticket": None,
            "purchased_return_ticket": None,
            "flight_completed": False,
        }


        # Invoke the flight graph with the new state
        flight_state = flight_graph.invoke(new_state, config=config)

        # Get the last message from the flight state
        last_message = flight_state["messages"][-1]
        # We expect the last message to be an ai message that greets the user
        assert last_message.type == "ai"

        # Update the state and halt execution (END --> until next user interaction)
        return Command(update={"messages": [last_message], "flight_state": flight_state, "new": False}, goto=END)
    
    # If it's an ongoing conversation with the flight assistant
    else:
        # Get the current flight state
        flight_state = state["flight_state"]

        # If the flight assistant pipeline has been completed
        # It either completes as a result of successful ticket purchase or manager escalation
        if flight_state["flight_completed"]:
            
            # If it's completed with ticket purchase
            if flight_state["purchased_depart_ticket"] is not None:
                # Assert that the latest tool call was completed
                assert flight_state["latest_tool_call"]["status"] == "completed"
                # Gather trip and ticket details from the flight state
                trip_details = flight_state["latest_tool_call"]["args"]
                purchased_depart_ticket = flight_state["purchased_depart_ticket"]
                purchased_return_ticket = flight_state["purchased_return_ticket"]

                # Construct a system message to deliver back to the travel assistant on the conclusion and details of the flight booking
                handover_message = (f"This is a system message indicating that the user has completed their flight booking process. The flight assistant has now handed the user back to you (travel assistant) to provide them further assistance." +
                                  f"\n\nBelow are the user's trip and ticket details:" +
                                  f"\n- Trip details: {trip_details}" +
                                  f"\n- Departure ticket: {purchased_depart_ticket}" +
                                  f"\n- Return ticket: {purchased_return_ticket if purchased_return_ticket else 'None'}" +
                                  f"\n\nPlease generate a message that welcomes the user back to the travel assistant. Also, while providing further assistance, take user's trip and ticket details into account. For example, if the user is interested in booking a hotel or renting a car, they may want to align it with their flight dates and destinations.")
                
                # Update state and hand the user back to the travel assistant
                return Command(update={"messages": [SystemMessage(content=handover_message)], "intent": None, "new": True}, goto="travel_node")

            # If it's completed with manager escalation
            elif flight_state["selected_depart_flight"] is not None:
                # Assert that the last action taken was manager escalation
                assert flight_state["next_action"] == "manager_escalation"

                # Gather trip and selected flight details
                trip_details = flight_state["latest_tool_call"]["args"]
                selected_depart_flight = flight_state["selected_depart_flight"]
                selected_return_flight = flight_state["selected_return_flight"]

                # Construct a very similar handover message
                handover_message = (f"This is a system message indicating that the user has completed their flight searching process. The flight assistant has now handed the user back to you (travel assistant) to provide them further assistance." +
                                    f"\n\nThe user has not purchased the tickets yet, but they made their flight selections and asked for approval from their manager. Once the manager approves the selected flights, the tickets will be purchased. Below are the user's trip and selected flight details:"
                                  f"\n- Trip details: {trip_details}" +
                                  f"\n- Departure flight: {selected_depart_flight}" +
                                  f"\n- Return flight: {selected_return_flight if selected_return_flight else 'None'}" +
                                  f"\n\nPlease generate a message that welcomes the user back to the travel assistant. Also, while providing further assistance, take user's trip and selected flight details into account. For example, if the user is interested in booking a hotel or renting a car, they may want to align it with their flight dates and destinations.")
                
                # Update state and hand the user back to the travel assistant
                return Command(update={"messages": [SystemMessage(content=handover_message)], "intent": None, "new": True}, goto="travel_node")
        
        # If the flight assistant pipeline is still ongoing
        else:
            
            # Get the last message from the state
            last_message = state["messages"][-1]

            # If the last message is a user message
            if last_message.type == "human":
                # Append the user input to the flight assistant's messages
                flight_state["messages"].append(last_message)

                # Invoke the flight graph with the user input
                flight_state = flight_graph.invoke(input= flight_state, config=config)

                # Get the last message from the flight state
                last_flight_message = flight_state["messages"][-1]
                
                # If it's an ai response to the user input
                if last_flight_message.type == "ai":
                    # Update the state with the ai response and route back to the flight node
                    return Command(update={"messages": [last_flight_message], "flight_state": flight_state,}, goto="flight_node")
                else:
                    # Just update the flight state and route back to the flight node
                    return Command(update={"flight_state": flight_state}, goto="flight_node")
                
            # If the last message is an ai message
            elif last_message.type == "ai":
                # Just halt execution without any updates to state, until the next user input
                return Command(goto=END)

            else:
                # There shouldn't be an entry with a message type other than "human" or "ai" (system, tool) during an ongoing conversation with the flight assistant
                # Print the current state and raise an exception
                print(f"\nUNEXPECTED MESSAGE TYPE IN FLIGHT NODE ({last_message.type} -> should only be 'human' or 'ai') DURING ONGOING CONVERSATION!\nSTATE DURING EXCEPTION:\n")
                pretty_print_object(state)
                raise Exception(f"Unexpected message type {last_message.type} in flight node")


def car_node(state: TravelState) -> Command[Literal["travel_node"]]:

    # -------- ONCE THE CAR RENTAL ASSISTANT IS IMPLEMENTED, IT CAN BE INTEGRATED HERE --------

    # For now, the car node will only provide a system message indicating that car rental is not available, and route back to the travel node
    handover_message = "This is a system message indicating that the car rental assistance is currently unavailable. Therefore, the user has been redirected back to you (travel assistant). Please generate a message that informs the user of the situation and offer further assistance with other services they might need."
    
    # Update state and hand the user back to the travel assistant
    return Command(update={"messages": [SystemMessage(content=handover_message)], "intent": None}, goto="travel_node")


def hotel_node(state: TravelState) -> Command[Literal["travel_node"]]:
    
    # -------- ONCE THE HOTEL RESERVATION ASSISTANT IS IMPLEMENTED, IT CAN BE INTEGRATED HERE --------

    # For now, the hotel node will only provide a system message indicating that hotel reservation is not available, and route back to the travel node
    handover_message = "This is a system message indicating that the hotel reservation assistance is currently unavailable. Therefore, the user has been redirected back to you (travel assistant). Please generate a message that informs the user of the situation and offer further assistance with other services they might need."
    
    # Update state and hand the user back to the travel assistant
    return Command(update={"messages": [SystemMessage(content=handover_message)], "intent": None}, goto="travel_node")



# Build the graph
builder = StateGraph(TravelState)
builder.add_node("travel_node", travel_node)
builder.add_node("flight_node", flight_node)
builder.add_node("car_node", car_node)
builder.add_node("hotel_node", hotel_node)
builder.add_edge(START, "travel_node")

# Create memory
checkpointer = MemorySaver()
travel_graph = builder.compile(checkpointer=checkpointer)

if __name__ == "__main__":

    try:
        # Generate the graph image and save it to the current file's directory
        image_path = os.path.join(os.path.dirname(__file__), "travel_graph.png")
        travel_graph.get_graph().draw_mermaid_png(output_file_path=image_path)
    except Exception:
        pass


    # Create a config object with a unique thread_id for memory tracking, and other runtime information (user/session etc.)
    manager_info = {"name": "Ali", "id":12345678910, "email": "ali@langgraph.com"}
    user_info = {"name": "Kaan", "id":10987654321, "email": "kaan@langgraph.com", "manager": manager_info}
    config = {
        "configurable": {
            "thread_id": 1,
            "user": user_info,
        }
    }

    # Create initial state
    initial_state = {
        "messages": [],
        "travel_messages": [],
        "intent": None,
        "flight_state": None,
        "initial": True,
        "new": True
    }

    # Enter the conversation loop
    initialization = True
    while True:
        
        # Get input from the user
        user_input = input("\nUser: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        
        # At initialization
        if initialization == True:
            state = initial_state
            initialization = False
        # At later steps
        else:
            graph_state = travel_graph.get_state(config).values
            state = {**state, **graph_state}

        
        # print("\nSTATE BEFORE NEXT STREAM CALL:\n")
        # # pretty_print_object(state)
        # pretty_print_object({"flight_state": state["flight_state"], "intent": state["intent"]})


        # Invoke the graph with the user input and get the stream of responses
        stream = travel_graph.stream(
            input={**state, "messages": [HumanMessage(content=user_input)]},
            config=config,
            stream_mode="updates"
        )

        # For every step (a node's execution and its corresponding updates in the state) in the stream
        for step in stream:

            # For every state dictionary delta (dictionary of updated fields and update values)
            for state_delta in step.values():

                # If there is an update to the messages field in the state
                if (state_delta is not None) and ("messages" in state_delta):
                    # For every message in the list of message updates
                    for message in state_delta["messages"]:
                        # If the message is an ai response and contains content (not a tool call), print it back to the user
                        if message.type == "ai" and message.content != "":
                            print(f"\nAssistant: {message.content}")