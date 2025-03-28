import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from typing import Type, Optional, Any
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from langchain_core.runnables import RunnableConfig

from time import sleep


# Schema for the input to the ticket purchase tool
class TicketPurchaseInput(BaseModel):
    config: RunnableConfig = Field(..., description="Configuration dictionary with additional runtime information")
    depart_flight: dict[str, Any] = Field(..., description="Departure flight details")
    return_flight: Optional[dict[str, Any]] = Field(None, description="Return flight details (if two-way trip)")
    

class TicketPurchaseTool(BaseTool):
    name: str = "purchase_tickets"
    description: str = "Carries out the ticket purchase process for the user."
    args_schema: Type[BaseModel] = TicketPurchaseInput
    # response_format: str = "content_and_artifact"

    def _run(
        self,
        config,
        depart_flight,
        return_flight=None
    ) -> dict[str, Optional[str]]:
        """Purchase tickets for the user based on the provided flight details."""
        
        depart_ticket = None
        return_ticket = None

        # Retrieve user information from the configuration dictionary
        print("\nKullanici bilgileri aliniyor...")
        sleep(2)
        user_info = config["configurable"]["user"]
        print(f"""\nKullanici bilgileri alindi. Asagidaki kullanici icin bilet rezervasyonu yapiliyor:
              \033[1mIsim:\033[0m {user_info['name']}
              \033[1mTCKN:\033[0m {user_info['id']}""")
        
        # Simulate the ticket purchase process
        print("\n-------------------------GIDIS-------------------------------")
        counter = 1
        while True:
            if counter > 1:
                print("\nGecersiz secim. Lutfen 20-100 arasi bir koltuk numarasi girin.")

            # Prompt the user to select a seat for the departure flight
            prompt_text = f"\nLutfen \033[1m({depart_flight['flight_code']})\033[0m kodlu gidis ucusunuz icin koltuk secimi yapin (20-100): "
            user_choice = input(prompt_text)

            try:
                # Simulate request and response flow from the airline's system
                if int(user_choice) >= 20 and int(user_choice) <= 100:
                    print("\nKoltuk secimi isleniyor...")
                    sleep(4)
                    print("\nRezervasyon tamamlaniyor...")
                    sleep(4)
                    print("\nRezervasyonunuz tamamlandi. Biletiniz basariyla olusturuldu:")
                    depart_ticket_str = f"\033[1mIsim:\033[0m {user_info['name']} | \033[1mUcus Kodu:\033[0m {depart_flight['flight_code']} | \033[1mKoltuk Numarasi:\033[0m {user_choice} | \033[1mPNR No:\033[0m X36Q9C"
                    print(f"\nBilet bilgileri --> {depart_ticket_str}")
                    print(f"\nBilet detaylariniz e-posta adresinize gonderildi: {user_info['email']}")

                    depart_ticket = {**depart_flight, "seat_number": int(user_choice), "pnr_number": "X36Q9C"}
                    
                    break
                else:
                    counter += 1
                    continue

            except:
                counter += 1
                continue

        # Repeat for the return flight if it exists
        if return_flight is not None:
            print("\n-------------------------DONUS-------------------------------")
            counter = 1
            while True:
                if counter > 1:
                    print("\nGecersiz secim. Lutfen 20-100 arasi bir koltuk numarasi girin.")

                # Prompt the user to select a seat for the departure flight
                prompt_text = f"\nLutfen \033[1m({return_flight['flight_code']})\033[0m kodlu donus ucusunuz icin koltuk secimi yapin (20-100): "
                user_choice = input(prompt_text)

                try:
                    # Simulate request and response flow from the airline's system
                    if int(user_choice) >= 20 and int(user_choice) <= 100:
                        print("\nKoltuk secimi isleniyor...")
                        sleep(4)
                        print("\nRezervasyon tamamlaniyor...")
                        sleep(4)
                        print("\nRezervasyonunuz tamamlandi. Biletiniz basariyla olusturuldu:")
                        return_ticket_str = f"\033[1mIsim:\033[0m {user_info['name']} | \033[1mUcus Kodu:\033[0m {return_flight['flight_code']} | \033[1mKoltuk Numarasi:\033[0m {user_choice} | \033[1mPNR No:\033[0m H62Y8A"
                        print(f"\n{return_ticket_str}")
                        print(f"\nBilet detaylariniz e-posta adresinize gonderildi: {user_info['email']}")

                        return_ticket = {**return_flight, "seat_number": int(user_choice), "pnr_number": "H62Y8A"}
                        
                        break
                    else:
                        counter += 1
                        continue

                except:
                    counter += 1
                    continue

        purchased_tickets = {"depart_ticket": depart_ticket, "return_ticket": return_ticket}

        return purchased_tickets


if __name__ == "__main__":
    
    ticket_purchase_tool = TicketPurchaseTool()

    manager_info = {"name": "Ali", "id":12345678910, "email": "ali@langgraph.com"}

    user_info = {"name": "Kaan", "id":10987654321, "email": "kaan@langgraph.com", "manager_info": manager_info}

    config = config = {"configurable": {"thread_id": "1", "user_info" : user_info}}

    depart_flight = {"airline": "THY", "departure_time": "05:30", "arrival_time": "07:15", "duration": "1h 45m", "class": "Business", "price": 5000, "flight_code": "TK802"}
    return_flight = {"airline": "THY", "departure_time": "09:00", "arrival_time": "10:20", "duration": "1h 20m", "class": "Economy", "price": 1500, "flight_code": "TK801"}

    # output = ticket_purchase_tool.invoke({"config":config, "depart_flight":depart_flight, "return_flight":return_flight})
    # output = ticket_purchase_tool.invoke({"config":config, "depart_flight":depart_flight, "return_flight":None})
    output = ticket_purchase_tool.invoke({"config":config, "depart_flight":depart_flight})

    print("---------------------------------------")
    print(f"Output type:\n\n {type(output)}\n\n")
    print("---------------------------------------")
    print(f"Output:\n\n {output}\n\n")
    print("---------------------------------------")
    # print(f"Output instance variables:\n\n {output.__dict__.keys()}\n\n")
    print(f"Depart ticket:\n\n {output['depart_ticket']}\n\n")
    print(f"Return ticket:\n\n {output['return_ticket']}\n\n")