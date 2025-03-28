import os
import sqlite3
from datetime import datetime
import random
from setup_mock_flight_data import normalized_cities, airlines, departure_times, durations, classes, prices, get_arrival_time, get_duration_string, day_generator



def create_and_connect_database(database_path):
    # Ensure the required directories exist
    os.makedirs(os.path.dirname(database_path), exist_ok=True)

    # Connect to SQLite database (or create it if it doesn't exist)
    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    # Check if the table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flights';")
    table_exists = cursor.fetchone() is not None

    # If it does, return directly
    if table_exists:
        print("Flights table already exists, skipping creation.")
        return
    # If it doesn't, create the table
    else:
        print("Creating flights table...")
        cursor.execute("""
            CREATE TABLE flights (
                flight_id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                from_city TEXT NOT NULL,
                to_city TEXT NOT NULL,
                airline TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                duration TEXT NOT NULL,
                flight_class TEXT NOT NULL,
                price INTEGER NOT NULL,
                flight_code TEXT NOT NULL
            );
        """)

        # Create indexes on date, from_city, and to_city columns for faster searches (behaves like table partitioning)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flight_date ON flights(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flight_from_city ON flights(from_city);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flight_to_city ON flights(to_city);")

    # Commit changes and close the connection
    connection.commit()
    
    return connection


# Function to generate a batch of flights to be inserted into the database
# Since around 5 million flights will be generated, we will insert them in batches for performance/memory reasons
def flight_batch_generator():
    # Assign a different id to each flight object, to be used as the primary key in the database
    flight_id = 0

    # Start creating sythetic flight objects (for each city pair, create 3 flights per day)
    # For each day
    for date in day_generator():
        # Initialize a new empty list (a new batch for each day)
        flight_objects_batch = []

        # From each city
        for from_city in normalized_cities:
            
            # To every other city
            for to_city in normalized_cities:
                
                # Don't create flights from a city to itself
                if from_city == to_city:
                    continue

                # Create 3 flights
                for i in range(3):

                    # Select an airline randomly such that in every 20 flights;
                    # 9 are THY, 7 are Pegasus, 3 are AJet, and 1 is SunExpress
                    num = random.randint(1, 20)
                    if (num == 20):
                        airline = "SunExpress"
                    elif (num >= 17):
                        airline = "AJet"
                    elif (num >= 10):
                        airline = "Pegasus"
                    else:
                        airline = "THY"
                    # Get next flight code for the selected airline
                    flight_code = airlines[airline].get_next_flight_code()

                    # Select a time for the flight such that;
                    # 70% percent of the flights are in busy hours
                    if random.random() < 0.7:
                        # Select a random busy hour
                        departure_time = random.choice(list(departure_times["busy"]))
                    else:
                        # Select a random quiet hour
                        departure_time = random.choice(list(departure_times["quiet"]))

                    # Select a random duration (in minutes) for the flight
                    duration_mins = random.choice(list(durations))
                    # And convert to a string (e.g. "1h 30m")
                    duration = get_duration_string(duration_mins)

                    # Calculate the arrival time based on the departure time and duration
                    arrival_time = get_arrival_time(departure_time, duration_mins)

                    # Select every 2nd one of the 3 flights as Business class
                    if (i == 1):
                        flight_class = "Business"
                        # And select a random price from the price list of Business class
                        price = random.choice(list(prices["Business"]))
                    # Apply similar logic for the other 2 flights as Economy class
                    else:
                        flight_class = "Economy"
                        price = random.choice(list(prices["Economy"]))

                    
                    # Set new id for each flight
                    flight_id += 1

                    # Create a new flight object with the generated data
                    new_flight_object = {
                        "flight_id" : flight_id,
                        "date" : date.strftime("%Y-%m-%d"),
                        "from_city" : from_city,
                        "to_city" : to_city,
                        "airline" : airline,
                        "departure_time" : departure_time,
                        "arrival_time" : arrival_time,
                        "duration" : duration,
                        "flight_class" : flight_class,
                        "price" : price,
                        "flight_code" : flight_code,
                    }

                    # Append the new flight object to the batch
                    flight_objects_batch.append(new_flight_object)
        
        # Yield the batch of flight objects for this day
        yield flight_objects_batch


def insert_batch_to_table(connection, batch):
    # Create the cursor object
    cursor = connection.cursor()

    # Define the query to insert a new flight object
    insertion_query = """
        INSERT INTO flights (flight_id, date, from_city, to_city, airline, departure_time, arrival_time, duration, flight_class, price, flight_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    # Create a list of tuples from the batch ('executemany' method expects input in this format, 
    # where each tuple represents a row to be inserted into the table)
    values = [(flight["flight_id"], flight["date"], flight["from_city"], flight["to_city"], flight["airline"], flight["departure_time"], flight["arrival_time"], flight["duration"], flight["flight_class"], flight["price"], flight["flight_code"]) for flight in batch]

    # Insert the values into the database table
    cursor.executemany(insertion_query, values)

    # Commit the changes
    connection.commit()



if __name__ == "__main__":
    # Define path to database file based on current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    database_path = os.path.join(current_dir, "db", "flight_database.db")

    # Create and connect to the database
    connection = create_and_connect_database(database_path)

    # Variables to keep track of the number of flights added to the database and the total time taken
    total = 0
    start = datetime.now()

    # Generate batch of flight data and insert into the database
    for batch in flight_batch_generator():
        insert_batch_to_table(connection, batch)
        total += len(batch)

    # Close database connection
    connection.close()

    # Calculate the total time taken
    end = datetime.now()
    elapsed_seconds = (end - start).total_seconds()

    # Print information about the process
    print(f"Generated and inserted '{total:,}' flights into the database in {int(elapsed_seconds // 60)} minutes {int(elapsed_seconds % 60)} seconds.")





