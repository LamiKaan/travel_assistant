import os
from langchain_core.messages import HumanMessage
from travel_graph import travel_graph

class TravelAssistant:
    def __init__(self, travel_graph, config):
        self.travel_graph = travel_graph
        self.config = config

    def generate_graph_image(self):
        try:
            # Generate the graph image and save it to the current file's directory
            image_path = os.path.join(os.path.dirname(__file__), "travel_graph.png")
            self.travel_graph.get_graph().draw_mermaid_png(output_file_path=image_path)
        except Exception:
            pass
        

    def start_chat(self):

        self.generate_graph_image()

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
                graph_state = self.travel_graph.get_state(self.config).values
                state = {**state, **graph_state}


            # Invoke the graph with the user input and get the stream of responses
            stream = self.travel_graph.stream(
                input={**state, "messages": [HumanMessage(content=user_input)]},
                config=self.config,
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



if __name__ == "__main__":

    # Create a config object with a unique thread_id for memory tracking, and other runtime information (user/session etc.)
    manager_info = {"name": "Ali", "id":12345678910, "email": "ali@langgraph.com"}
    user_info = {"name": "Kaan", "id":10987654321, "email": "kaan@langgraph.com", "manager": manager_info}
    config = {
        "configurable": {
            "thread_id": 1,
            "user": user_info,
        }
    }

    travel_assistant = TravelAssistant(travel_graph, config)

    travel_assistant.start_chat()