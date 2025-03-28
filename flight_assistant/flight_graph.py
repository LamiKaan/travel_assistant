import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import json

from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig

from typing import Annotated, Any, Optional, List
from typing_extensions import TypedDict, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langgraph.pregel.io import AddableValuesDict

from flight_assistant.tools.flight_search import FlightSearchTool
from flight_assistant.tools.ticket_purchase import TicketPurchaseTool
from flight_assistant.tools.manager_escalation import ManagerEscalationTool
from flight_assistant.flight_agent import flight_llm, flight_prompt
from flight_assistant.utils import pretty_print_object
from policy_assistant.policy_agent import policy_llm


# -----------------------------------------------------------------------------------
# Create tool instances
flight_search_tool = FlightSearchTool()
ticket_purchase_tool = TicketPurchaseTool()
manager_escalation_tool = ManagerEscalationTool()
# -----------------------------------------------------------------------------------


# -----------------------------------------------------------------------------------
# Define the schema for the state of the graph with state variables
class FlightState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    # Variable to store the "tool_call" dictionary for the tool that is expected to be called next
    latest_tool_call: Optional[dict[str, Any]]
    # Variable that shows the (potential) next step to complete in the flight agent pipeline
    # Should be one of either "flight_search", "ticket_purchase", and (potentially) "manager_escalation"
    next_action: Literal["flight_search", "ticket_purchase", "manager_escalation"]
    # Variables to store the flight search results retrieved by the flight search tool
    retrieved_depart_flights: Optional[List[dict[str, Any]]]
    retrieved_return_flights: Optional[List[dict[str, Any]]]
    # Variables to store the selected flight details for ticket purchase
    selected_depart_flight: Optional[dict[str, Any]]
    selected_return_flight: Optional[dict[str, Any]]
    # Variable to store the message that user wants to send to the manager
    escalation_message: Optional[str]
    # Variables to store the purchased ticket details
    purchased_depart_ticket: Optional[dict[str, Any]]
    purchased_return_ticket: Optional[dict[str, Any]]
    # Variable to mark the end of the flight agent pipeline
    flight_completed: bool
# -----------------------------------------------------------------------------------

# -----------------------------------------------------------------------------------
def flight_search_node(state: FlightState) -> Command[Literal["flight_agent", "human_tool_reviewer"]]:
    # Get the latest tool call from the state
    latest_tool_call = state["latest_tool_call"]
    # Assert the tool name and status of the tool call
    assert latest_tool_call["name"] == "search_flights"
    assert latest_tool_call["status"] == "approved"

    # Inject the tool_call_id (InjectedToolArg) in addition to the existing arguments of the tool call
    latest_tool_call["args"] = {"tool_call_id": latest_tool_call["id"], **latest_tool_call["args"]}

    # Invoke the tool with constructed arguments and get the tool response
    tool_response = flight_search_tool.invoke(latest_tool_call)

    # If tool returned a successful response
    if tool_response.status == "success":
        # Convert the content (string) of the tool response to a dictionary
        results = json.loads(tool_response.content)
        # Get the retrieved flight details from the tool response
        retrieved_depart_flights = results["depart_flights"]
        retrieved_return_flights = results["return_flights"]

        # Mark latest tool call status as completed
        latest_tool_call["status"] = "completed"

        print("\nTesekkurler. Simdi sizin icin ucuslari listeleyecegim. Lutfen secenekleri inceleyin ve size en uygun ucusu secin.")

        # Update the state with tool response, latest tool call, the retrieved flight details and next action set as ticket purchase. Route back to the human tool reviewer to continue with the ticket selection and purchase process.
        return Command(update={"messages": [tool_response], "latest_tool_call": latest_tool_call, "retrieved_depart_flights": retrieved_depart_flights, "retrieved_return_flights": retrieved_return_flights, "next_action": "ticket_purchase"}, goto="human_tool_reviewer")
    
    # If tool returned an unsuccessful response
    else:
        # Assert that tool response status is "error"
        assert tool_response.status == "error"

        # Mark latest tool call status as failed
        latest_tool_call["status"] = "failed"

        # Update the state with the tool response and latest tool call, and route back to the flight agent for llm to take further action upon tool error
        return Command(update={"messages": [tool_response], "latest_tool_call": latest_tool_call}, goto="flight_agent")
# -----------------------------------------------------------------------------------


# -----------------------------------------------------------------------------------
def ticket_purchase_node(state: FlightState, config: RunnableConfig) -> Command[Literal["flight_agent", "ticket_purchase_node"]]:

    # Purchase tickets for the user based on the selected flight details
    try:
        # Get the selected depart and return flight details from the state
        selected_depart_flight = state["selected_depart_flight"]
        selected_return_flight = state["selected_return_flight"]

        # Invoke the ticket purchase tool with the selected flight details and the configuration dictionary (which may contain additional runtime information like user or session info etc.)
        result = ticket_purchase_tool.invoke({"config": config, "depart_flight": selected_depart_flight, "return_flight": selected_return_flight})

        # Construct a system message to deliver back to flight_llm on the completion and details of the flight booking
        completion_message = (f"This is a system message indicating that the user has successfully completed their flight booking process." +
                            f"\n\nBelow are the details of the trip and the tickets they've purchased:" +
                            f"\n- Trip information: {state['latest_tool_call']['args']}" +
                            f"\n- Departure ticket: {selected_depart_flight}" +
                            f"\n- Return ticket: {selected_return_flight}" +
                            f"\n\nIf the user has additional travel plans and wishes to book more flights, continue assisting them accordingly.")

        # If the ticket purchase carried out, save purchased tickets to the state
        # Then, mark the flight pipeline as completed and route back to the flight agent node
        return Command(update={"messages": [SystemMessage(content=completion_message)], "purchased_depart_ticket": result["depart_ticket"], "purchased_return_ticket": result["return_ticket"], "flight_completed": True}, goto="flight_agent")
    
    except Exception as e:
        # Inform user
        print(f"\nBilet satin alma islemi sirasinda bir hata olustu: {str(e)}. \nTekrar deneniyor...")

        # And try again by routing back to this node with the same state
        return Command(goto="ticket_purchase_node")
# -----------------------------------------------------------------------------------


# -----------------------------------------------------------------------------------
def manager_escalation_node(state: FlightState, config: RunnableConfig) -> Command[Literal["flight_agent", "manager_escalation_node"]]:
    
    # Send request to manager (with additional explanatory message) to purchase tickets that violate company policy
    try:
        # Get the selected depart and return flight details from the state
        selected_depart_flight = state["selected_depart_flight"]
        selected_return_flight = state["selected_return_flight"]

        # Get the escalation message from the state
        escalation_message = state["escalation_message"]

        # Invoke the manager escalation tool
        result = manager_escalation_tool.invoke({"config": config, "depart_flight": selected_depart_flight, "return_flight": selected_return_flight, "escalation_message": escalation_message})

        # Construct a system message to deliver back to flight_llm on the completion and details of the flight booking
        completion_message = (f"This is a system message indicating that the user has completed their flight booking process." +
                            f"\n\nBelow are the details of the trip and the tickets they've selected:" +
                            f"\n- Trip information: {state['latest_tool_call']['args']}" +
                            f"\n- Departure ticket: {selected_depart_flight}" +
                            f"\n- Return ticket: {selected_return_flight}" +
                            f"\n\nIf the user has additional travel plans and wishes to book more flights, continue assisting them accordingly.")

        # Once it's complete, mark the flight pipeline as completed and route back to the flight agent node
        return Command(update={"messages": [SystemMessage(content=completion_message)], "flight_completed": True}, goto="flight_agent")
    
    except Exception as e:
        # Inform user
        print(f"\nOnay talebi sirasinda bir hata olustu: {str(e)}. \nTekrar deneniyor...")

        # And try again by routing back to this node with the same state
        return Command(goto="manager_escalation_node")
# -----------------------------------------------------------------------------------


# -----------------------------------------------------------------------------------
def policy_control_node(state: FlightState) -> Command[Literal["ticket_purchase_node", "human_tool_reviewer"]]:
    # Get the selected depart and return flight details from the state
    selected_depart_flight = state["selected_depart_flight"]
    selected_return_flight = state["selected_return_flight"]

    # Check if the selected flights comply with the company policy
    print("\nSectiginiz ucuslarin sirket politikasina uygunlugu kontrol ediliyor...")

    policy_violation = False

    # Invoke the policy agent with the selected flight details and get the results of the policy check
    result_depart = policy_llm.invoke({"input": selected_depart_flight})
    if result_depart["complies"] == False:
        policy_violation = True
        print("\n\nUzgunum, sectiginiz ucuslar sirket politikasina uygun degil.")
        print(f"\nGidis ucusu \033[1m({selected_depart_flight['flight_code']})\033[0m asagidaki politikalara uymamaktadir:\n{result_depart['details']}")
    
    if selected_return_flight is not None:
        result_return = policy_llm.invoke({"input": selected_return_flight})

        if result_return["complies"] == False and policy_violation == True:
            print(f"\nDonus ucusu \033[1m({selected_return_flight['flight_code']})\033[0m asagidaki politikalara uymamaktadir:\n{result_return['details']}")
        elif result_return["complies"] == False and policy_violation == False:
            policy_violation = True
            print("\n\nUzgunum, sectiginiz ucuslar sirket politikasina uygun degil.")
            print(f"\nDonus ucusu \033[1m({selected_return_flight['flight_code']})\033[0m asagidaki politikalara uymamaktadir:\n{result_return['details']}")

    # If the selected flights violate the policy
    if policy_violation:
        counter = 1
        
        while True:
            if counter > 1:
                print("\nGecersiz secim. Lutfen 1, 0 veya 2 tuslayin.")

            # Prompt the user to select one of the three possible option: escalate to manager, change selected flights, or search for new flights
            prompt_text = "\n\nYoneticinizden istisna onay sureci talebinde bulunmak icin 1, ucus secimlerinizi degistirmek icin 0, arama kriterlerinizi degistirmek ve baska ucuslar aramak icin 2 tuslayin: "
            print(prompt_text)
            user_choice = input()

            # If the user wants to escalate to manager
            if user_choice == "1":
                # Update next action to manager_escalation and route to the human tool reviewer node to approve/reject escalation
                return Command(update={"next_action": "manager_escalation"}, goto="human_tool_reviewer")
            # If the user wants to change the selected flights
            elif user_choice == "0":
                # Discard the selected flights and route back to human_tool_reviewer to prompt the user for new flight selection (keeping retrieved flights the same)
                return Command(update={"selected_depart_flight": None, "selected_return_flight": None}, goto="human_tool_reviewer")
            # If the user wants to change the search criteria and search for new flights
            elif user_choice == "2":
                # Generate a synthetic user message to convey the user's intention to search for new flights
                synth_user_message = HumanMessage(content="Arama kriterlerimi degistirmek ve baska ucuslar aramak istiyorum.")

                # Add this to the state messages to trigger the flight agent for a response
                # Reset all retrieved and selected flights, set the next action to flight search,
                # and route back to the flight agent node
                return Command(update={"messages": [synth_user_message], "retrieved_depart_flights": None, "retrieved_return_flights": None, "selected_depart_flight": None, "selected_return_flight": None, "next_action": "flight_search"}, goto="flight_agent")
            # If the user entered an invalid choice
            else:
                counter += 1
                continue

    # If the selected flights comply with the policy
    else:
        # Route to the ticket purchase node to proceed with the ticket purchase process
        print("\nSectiginiz ucuslar sirket politikasina uygundur. Bilet satin alma islemine devam ediliyor...")
        return Command(goto="ticket_purchase_node")
# -----------------------------------------------------------------------------------


# -----------------------------------------------------------------------------------
# Node to prompt the user to review and approve/reject the tool calls, and manage their routing
def human_tool_reviewer(state: FlightState) -> Command[Literal["flight_agent", "flight_search_node", "policy_control_node","ticket_purchase_node", "manager_escalation_node", "human_tool_reviewer"]]:

    # Get the next action to be taken from the state
    next_action = state["next_action"]

    # If the next action is to search for flights
    if next_action == "flight_search":
        # Get the last message and latest tool call from the state
        last_message = state["messages"][-1]
        latest_tool_call = state["latest_tool_call"]
        # Assert that they refer to the same tool call (same id), and that the tool call is pending
        assert last_message.tool_calls[0]["id"] == latest_tool_call["id"]
        assert latest_tool_call["status"] == "pending"

        # Get the arguments of the tool call
        args = latest_tool_call["args"]

        prompt_text = (f"\nBu bilgilerle ucus aramasi yapmami onayliyor musunuz?" + 
        f"\n- \033[1mNereden:\033[0m {args['from_city']}" +
        f"\n- \033[1mNereye:\033[0m {args['to_city']}" +
        f"\n- \033[1mUcus tipi:\033[0m {'Gidis-Donus' if args['flight_type']=='two-way' else 'Tek yon'}" +
        f"\n- \033[1mGidis tarihi:\033[0m {args['depart_date']}" +
        f"\n- \033[1mDonus tarihi:\033[0m {args['return_date'] if args['flight_type']=='two-way' else '---'}" +
        f"\n\nOnaylamak icin 1, reddetmek icin 0 tuslayin: ")
        print(prompt_text)
        user_choice = input()

        # If the user approved the tool call
        if user_choice == "1":
            # Update the status of the tool call to "approved" and route to the flight search node
            latest_tool_call["status"] = "approved"
            return Command(update={"latest_tool_call": latest_tool_call}, goto="flight_search_node")
        # If the user rejected the tool call
        elif user_choice == "0":
            # Update the status of the tool call to "rejected"
            latest_tool_call["status"] = "rejected"
            # Construct a tool response to notify the flight agent that the tool call was rejected
            tool_response = ToolMessage(
                tool_call_id=latest_tool_call["id"],
                content="The user has manually rejected the tool call for searching flights with the current parameters. This is not an error — it indicates that the user likely wants to update or change the search criteria (e.g., different dates, destinations). Please acknowledge the rejection gracefully and ask the user how they'd like to proceed or what they'd like to change about their request.",
                status = "error"
            )
            # Update the state with the tool response and route back to the flight agent node
            return Command(update={"messages": [tool_response]}, goto="flight_agent")
        # If the user entered an invalid choice
        else:
            # Route back to this node to prompt the user again
            print("\nGecersiz secim, lutfen 1 veya 0 tuslayin.")
            return Command(goto="human_tool_reviewer")
        
    # If the next action is to select tickets
    elif next_action == "ticket_purchase":
        # If a depart flight is not selected yet
        if state["selected_depart_flight"] is None:
            # Get the retrieved flight details from the state
            retrieved_depart_flights = state["retrieved_depart_flights"]

            # Get options for departure
            depart1, depart2, depart3 = retrieved_depart_flights
            
            # Lutfen seciminizi tuslayin (1, 2 veya 3): """
            prompt_text = (f"\nLutfen asagidaki gidis ucuslarindan birini secin:" +
            f"\n1- \033[1mHavayolu:\033[0m {depart1['airline']} | \033[1mKalkis:\033[0m {depart1['departure_time']} | \033[1mVaris:\033[0m {depart1['arrival_time']} | \033[1mSure:\033[0m {depart1['duration']} | \033[1mKabin:\033[0m {depart1['class']} | \033[1mFiyat:\033[0m {depart1['price']} TL | \033[1mKod:\033[0m {depart1['flight_code']}" +
            f"\n2- \033[1mHavayolu:\033[0m {depart2['airline']} | \033[1mKalkis:\033[0m {depart2['departure_time']} | \033[1mVaris:\033[0m {depart2['arrival_time']} | \033[1mSure:\033[0m {depart2['duration']} | \033[1mKabin:\033[0m {depart2['class']} | \033[1mFiyat:\033[0m {depart2['price']} TL | \033[1mKod:\033[0m {depart2['flight_code']}" +
            f"\n3- \033[1mHavayolu:\033[0m {depart3['airline']} | \033[1mKalkis:\033[0m {depart3['departure_time']} | \033[1mVaris:\033[0m {depart3['arrival_time']} | \033[1mSure:\033[0m {depart3['duration']} | \033[1mKabin:\033[0m {depart3['class']} | \033[1mFiyat:\033[0m {depart3['price']} TL | \033[1mKod:\033[0m {depart3['flight_code']}" +
            f"\n\nLutfen seciminizi tuslayin (1, 2 veya 3): ")
            print(prompt_text)
            user_choice = input()

            # If the user made a valid departure selection
            if user_choice in ["1", "2", "3"]:
                # Get the selected depart flight details
                selected_depart_flight = retrieved_depart_flights[int(user_choice)-1]
                # Update the state with the selected depart flight and route back to this node to prompt the user for return flight selection (if two-way trip)
                return Command(update={"selected_depart_flight": selected_depart_flight}, goto="human_tool_reviewer")
            # If the user entered an invalid choice
            else:
                # Route back to this node to prompt the user again
                print("\nGecersiz secim. Lutfen 1, 2 veya 3 tuslayin.")
                return Command(goto="human_tool_reviewer")
            
        # If it's a two-way tip and a depart flight is already selected, but a return flight is not selected yet
        elif len(state["retrieved_return_flights"]) > 0 and state["selected_return_flight"] is None:
            # Get the retrieved flight details from the state
            retrieved_return_flights = state["retrieved_return_flights"]

            # Get options for return
            return1, return2, return3 = retrieved_return_flights
            
            # Lutfen seciminizi tuslayin (1, 2 veya 3): """
            prompt_text = (f"\nLutfen asagidaki donus ucuslarindan birini secin:" +
            f"\n1- \033[1mHavayolu:\033[0m {return1['airline']} | \033[1mKalkis:\033[0m {return1['departure_time']} | \033[1mVaris:\033[0m {return1['arrival_time']} | \033[1mSure:\033[0m {return1['duration']} | \033[1mKabin:\033[0m {return1['class']} | \033[1mFiyat:\033[0m {return1['price']} TL | \033[1mKod:\033[0m {return1['flight_code']}" +
            f"\n2- \033[1mHavayolu:\033[0m {return2['airline']} | \033[1mKalkis:\033[0m {return2['departure_time']} | \033[1mVaris:\033[0m {return2['arrival_time']} | \033[1mSure:\033[0m {return2['duration']} | \033[1mKabin:\033[0m {return2['class']} | \033[1mFiyat:\033[0m {return2['price']} TL | \033[1mKod:\033[0m {return2['flight_code']}" +
            f"\n3- \033[1mHavayolu:\033[0m {return3['airline']} | \033[1mKalkis:\033[0m {return3['departure_time']} | \033[1mVaris:\033[0m {return3['arrival_time']} | \033[1mSure:\033[0m {return3['duration']} | \033[1mKabin:\033[0m {return3['class']} | \033[1mFiyat:\033[0m {return3['price']} TL | \033[1mKod:\033[0m {return3['flight_code']}" +
            f"\n\nLutfen seciminizi tuslayin (1, 2 veya 3): ")
            print(prompt_text)
            user_choice = input()

            # If the user made a valid return selection
            if user_choice in ["1", "2", "3"]:
                # Get the selected depart flight details
                selected_return_flight = retrieved_return_flights[int(user_choice)-1]
                # Update the state with the selected return flight and route back to this node to prompt the user for final review before ticket purchase
                return Command(update={"selected_return_flight": selected_return_flight}, goto="human_tool_reviewer")
            # If the user entered an invalid choice
            else:
                # Route back to this node to prompt the user again
                print("\nGecersiz secim. Lutfen 1, 2 veya 3 tuslayin.")
                return Command(goto="human_tool_reviewer")
        
        # If the user is done with selecting flights
        else:
            # Get the selected depart and return flight details from the state
            selected_depart_flight = state["selected_depart_flight"]
            selected_return_flight = state["selected_return_flight"]

            # Prompt the user to review the selected flights and approve/reject to proceed with the ticket purchase

            prompt_text = (f"\nSectiginiz ucuslar:" +
            f"\n- \033[1mUcus:\033[0m Gidis | \033[1mKod:\033[0m {selected_depart_flight['flight_code']}")
            if selected_return_flight is not None:
                prompt_text += f"\n- \033[1mUcus:\033[0m Donus | \033[1mKod:\033[0m {selected_return_flight['flight_code']}"
            prompt_text += "\n\nBu secimleri onayliyor musunuz?\nOnaylamak icin 1, ucus secimlerinizi degistirmek icin 0,  arama kriterlerinizi degistirmek ve baska ucuslar aramak icin 2 tuslayin: "
            print(prompt_text)
            user_choice = input()

            # If the user approved the selected flights
            if user_choice == "1":
                # Route to the policy control node to check the compliance of the selected flights with the company policy
                return Command(goto="policy_control_node")
            # If the user wants to change the selected flights
            elif user_choice == "0":
                # Discard the selected flights and route back to this node to prompt the user for new flight selection (keeping retrieved flights the same)
                return Command(update={"selected_depart_flight": None, "selected_return_flight": None}, goto="human_tool_reviewer")
            # If the user wants to change the search criteria and search for new flights
            elif user_choice == "2":
                # Generate a synthetic user message to convey the user's intention to search for new flights
                synth_user_message = HumanMessage(content="Arama kriterlerimi degistirmek ve baska ucuslar aramak istiyorum.")

                # Add this to the state messages to trigger the flight agent for a response
                # Reset all retrieved and selected flights, set the next action to flight search,
                # and route back to the flight agent node
                return Command(update={"messages": [synth_user_message], "retrieved_depart_flights": None, "retrieved_return_flights": None, "selected_depart_flight": None, "selected_return_flight": None, "next_action": "flight_search"}, goto="flight_agent")
            # If the user entered an invalid choice
            else:
                # Route back to this node to prompt the user again
                print("\nGecersiz secim. Lutfen 1, 0 veya 2 tuslayin.")
                return Command(goto="human_tool_reviewer")
            
    # If the next action is to escalate to manager
    else:
        # Prompt the user to enter an additional message to the manager
        prompt_text = "\nIstisna onay surecinizle ilgili yoneticinize iletmek istediginiz ek bir mesaj varsa yaziniz (yoksa bos birakabilirsiniz): \n"
        escalation_message = None if (user_input := input(prompt_text)).strip() == "" else user_input.strip()

        counter = 1
        while True:
            if counter > 1:
                print("\nGecersiz secim. Lutfen 1, 0, 2 veya 3 tuslayin.")

            # Prompt the user to approve/reject the escalation
            prompt_text = f"\nTalebinizi yoneticinize gondermek icin 1, ucus secimlerinizi degistirmek icin 0,  arama kriterlerinizi degistirmek ve baska ucuslar aramak icin 2 tuslayin. {'Yoneticinize iletilecek mesajinizi degistirmek' if escalation_message else 'Yoneticinize gondermek uzere ek bir mesaj eklemek'} icin 3 tuslayin: "
            print(prompt_text)
            user_choice = input()

            # If the user approved the escalation
            if user_choice == "1":
                # Update the escalation message in the state and route to the manager escalation node
                return Command(update={"escalation_message": escalation_message}, goto="manager_escalation_node")
            # If the user wants to change the selected flights
            elif user_choice == "0":
                # Discard the selected flights and route back to this node to prompt the user for new flight selection (keeping retrieved flights the same)
                return Command(update={"selected_depart_flight": None, "selected_return_flight": None, "next_action": "ticket_purchase"}, goto="human_tool_reviewer")
            # If the user wants to change the search criteria and search for new flights
            elif user_choice == "2":
                # Generate a synthetic user message to convey the user's intention to search for new flights
                synth_user_message = HumanMessage(content="Arama kriterlerimi degistirmek ve baska ucuslar aramak istiyorum.")

                # Add this to the state messages to trigger the flight agent for a response
                # Reset all retrieved and selected flights, set the next action to flight search,
                # and route back to the flight agent node
                return Command(update={"messages": [synth_user_message], "retrieved_depart_flights": None, "retrieved_return_flights": None, "selected_depart_flight": None, "selected_return_flight": None, "next_action": "flight_search"}, goto="flight_agent")
            # If the user wants to change the escalation message
            elif user_choice == "3":
                # Route back to the beginning of this node to prompt the user for a new escalation message
                return Command(goto="human_tool_reviewer")
            # If the user entered an invalid choice
            else:
                counter += 1
                continue
# -----------------------------------------------------------------------------------


# -----------------------------------------------------------------------------------
# Main node of the flight agent pipeline that handles user interactions and tool calls
def flight_agent(state: FlightState) -> Command[Literal["flight_agent", "human_tool_reviewer", END]]:
    
    # If the flight pipeline is completed, halt the pipeline (END --> until next user interaction)
    if state["flight_completed"]:
        return Command(goto=END)

    # Retrieve the last message from the state
    last_message = state["messages"][-1]

    # If the last message is a system message
    if last_message.type == "system":
        return Command(goto=END)
    
    # If the last message is a user, or tool message
    elif last_message.type in ["human", "tool"]:
        # Then invoke the llm with the current state messages and return the updated state
        response = flight_llm.invoke(state["messages"])
        return Command(update={"messages": [response]}, goto="flight_agent")
    
    # If the last message is an ai message
    else:
        # Get the valid and invalid tool calls attributes of the last message
        tool_calls = last_message.tool_calls
        invalid_tool_calls = last_message.invalid_tool_calls
        # Since we disabled parallel tool calls, there should be at most one tool call
        assert len(tool_calls) <= 1

        # If the last messaage is a valid tool call
        if tool_calls:
            # Get the tool call dictionary and associated tool name
            tool_call = tool_calls[0]
            tool_name = tool_call["name"]
            # Flight agent is bound only to the flight search tool, so this should be the only possible tool call
            assert tool_name == "search_flights"

            # Route to the human tool reviewer node which requests human approval before calling the tool (human in the loop)
            # Also, add an additional status key to the tool call dictionary to track its status
            tool_call["status"] = "pending"
            return Command(update={"latest_tool_call": tool_call, "next_action": "flight_search"}, goto="human_tool_reviewer")
    
        # If the last message is an invalid tool call (message type that llm can
        # handle by making further reasoning by itself)
        elif invalid_tool_calls:
            # Notify the user
            print("\n[Tool Error] Invalid tool call received:")
            pretty_print_object(invalid_tool_calls)

            # Then invoke the llm with the current state messages and return the updated state
            response = flight_llm.invoke(state["messages"])
            return Command(update={"messages": [response]}, goto="flight_agent")
    
        else:
            # Then the last message is assistant/ai type (which already is a response from the llm)
            # So there is no need for invocation, return the current state with no changes and halt the pipeline (END --> until next user interaction)
            return Command(goto=END)
# -----------------------------------------------------------------------------------



 # Build the graph
builder = StateGraph(FlightState)
builder.add_node("flight_agent", flight_agent)
builder.add_node("flight_search_node", flight_search_node)
builder.add_node("ticket_purchase_node", ticket_purchase_node)
builder.add_node("manager_escalation_node", manager_escalation_node)
builder.add_node("policy_control_node", policy_control_node)
builder.add_node("human_tool_reviewer", human_tool_reviewer)
builder.add_edge(START, "flight_agent")

# Create memory and compile the graph with the memory
checkpointer = MemorySaver()
flight_graph = builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":

    try:
        # Generate the graph image and save it to the current file's directory
        image_path = os.path.join(os.path.dirname(__file__), "flight_graph.png")
        flight_graph.get_graph().draw_mermaid_png(output_file_path=image_path)
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

    # Create initial state with a system message for context
    initial_state = {
        "messages": [SystemMessage(content=flight_prompt)],
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
    
    # Invoke graph once to initialize the state
    state = flight_graph.invoke(initial_state, config=config)

    # pretty_print_object(state)

    while True:
        
        # Get input from the user
        user_input = input("\nUser: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        graph_state = flight_graph.get_state(config).values
        if(graph_state["flight_completed"] == True):
            state = {**initial_state, "messages": graph_state["messages"]}
        else:
            state = {**state, **graph_state}
    
        # Invoke the graph with the user input and get the stream of responses
        stream = flight_graph.stream(
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
