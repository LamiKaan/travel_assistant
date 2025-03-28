import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from typing import Type, Optional, Any
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from langchain_core.runnables import RunnableConfig

from time import sleep

# Schema for the input to the manager escalation tool
class ManagerEscalationInput(BaseModel):
    config: RunnableConfig = Field(..., description="Configuration dictionary with additional runtime information")
    depart_flight: dict[str, Any] = Field(..., description="Departure flight details")
    return_flight: Optional[dict[str, Any]] = Field(None, description="Return flight details (if two-way trip)")
    escalation_message: Optional[str] = Field(None, description="Additional message to be sent to the manager in case of escalation")
    

class ManagerEscalationTool(BaseTool):
    name: str = "escalate_to_manager"
    description: str = "Carries out the manager escalation process for the user."
    args_schema: Type[BaseModel] = ManagerEscalationInput
    # response_format: str = "content_and_artifact"

    def _run(
        self,
        config,
        depart_flight,
        return_flight=None,
        escalation_message=None
    ) -> bool:
        """Send mail (with additional explanatory message) to the manager on behalf of the user, for requesting the purchase of flights that violate company policy."""

        # Retrieve user information from the configuration dictionary
        print("\nKullanici bilgileri aliniyor...")
        sleep(2)
        user_info = config["configurable"]["user"]
        print(f"\n\033[1mIsim:\033[0m {user_info['name']}\n\033[1mE-posta:\033[0m {user_info['email']}")

        # Retrieve manager information from the configuration dictionary
        print("\n\nYonetici bilgileri aliniyor...")
        sleep(2)
        manager_info = user_info["manager"]
        print(f"\n\033[1mIsim:\033[0m {manager_info['name']}\n\033[1mE-posta:\033[0m {manager_info['email']}")

        # Simulate the escalation process
        print("\n\nTalebiniz yoneticinize iletiliyor...")
        print(f"\n\033[1mFrom:\033[0m {user_info['name']}({user_info['email']})")
        print(f"\n\033[1mTo:\033[0m {manager_info['name']}({manager_info['email']})")
        print(f"\n\033[1mSubject:\033[0m {depart_flight['flight_code']}{' ve ' if return_flight else ''}{return_flight['flight_code'] if return_flight else ''} kodlu ucus{'lar' if return_flight else ''} icin onay talebi")
        print(f"\n\033[1mMessage:\033[0m {escalation_message if escalation_message else '-'}")
        sleep(4)
        print("\n\nIstisna talebiniz yoneticinize iletilmistir. Onay gelmesi halinde e-mail ile bilgilendirileceksiniz.")

        return True


if __name__ == "__main__":
    
    manager_escalation_tool = ManagerEscalationTool()

    manager_info = {"name": "Ali", "id":12345678910, "email": "ali@langgraph.com"}
    user_info = {"name": "Kaan", "id":10987654321, "email": "kaan@langgraph.com", "manager_info": manager_info}
    config = config = {"configurable": {"thread_id": "1", "user_info" : user_info}}

    depart_flight = {"airline": "THY", "departure_time": "05:30", "arrival_time": "07:15", "duration": "1h 45m", "class": "Business", "price": 5000, "flight_code": "TK802"}
    return_flight = {"airline": "THY", "departure_time": "09:00", "arrival_time": "10:20", "duration": "1h 20m", "class": "Economy", "price": 1500, "flight_code": "TK801"}

    escalation_message = "Bacagim kirildi. Ekstra bacak mesafesine ihtiyacim var. O yuzden business class ucus almaliyim."

    # output = ticket_purchase_tool.invoke({"config":config, "depart_flight":depart_flight, "return_flight":return_flight})
    # output = ticket_purchase_tool.invoke({"config":config, "depart_flight":depart_flight, "return_flight":None})
    output = manager_escalation_tool.invoke({"config":config, "depart_flight":depart_flight, "return_flight":None, "escalation_message":escalation_message})

    # print("---------------------------------------")
    # print(f"Output type:\n\n {type(output)}\n\n")
    # print("---------------------------------------")
    # print(f"Output:\n\n {output}\n\n")
    # print("---------------------------------------")
    # print(f"Output instance variables:\n\n {output.__dict__.keys()}\n\n")
    # print(f"Depart ticket:\n\n {output['depart_ticket']}\n\n")
    # print(f"Return ticket:\n\n {output['return_ticket']}\n\n")