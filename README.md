## Run locally on terminal

1. Clone the repo:
   ```bash
   git clone https://github.com/LamiKaan/travel_assistant.git
   ```
2. Navigate inside the project root directory:
   ```bash
   cd travel_assistant
   ```
3. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
   or
   ```bash
   python -m venv venv
   ```
4. Activate the environment:
   ```bash
   source venv/bin/activate
   ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Navigate inside the "flight_assistant/data" directory:
   ```bash
   cd flight_assistant/data
   ```
7. Run the "create_mock_flight_data" file to create the database for the mock flight data. This may take a couple of minutes:
   ```bash
   python create_mock_flight_data.py
   ```
8. Navigate back to the project root:
   ```bash
   cd ../..
   ```
9. Edit the ".env.example" file with a valid OpenAI API key and change file name to ".env".
   <br>
   <br>
10. Run the main file and start chatting:
    ```bash
    python main.py
    ```
11. To quit chat, type "exit" or "quit" to the user prompt:
    ```bash
    User: quit
    User: exit
    ```
