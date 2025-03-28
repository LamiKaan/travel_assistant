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
4. Activate it:
   ```bash
   source venv/bin/activate
   ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Edit the ".env.example" file with a valid OpenAI API key and change file name to ".env".

7. Run the main file and start chatting:
   ```bash
   python main.py
   ```
8. To quit chat, type "exit" or "quit" to the user prompt:
   ```bash
   User: quit
   User: exit
   ```
