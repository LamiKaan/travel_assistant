import unicodedata
from datetime import datetime, timedelta

# ---CITIES---

# List of citites with airports in Turkey
cities = [
    "Adana", "Adıyaman", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya", "Ardahan", 
    "Artvin", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", 
    "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", 
    "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", 
    "Gaziantep", "Giresun", "Gümüşhane", "Hakkâri", "Hatay", "Iğdır", "Isparta", 
    "İstanbul", "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", 
    "Kayseri", "Kırıkkale", "Kırklareli", "Kırşehir", "Kocaeli", "Konya", "Kütahya", 
    "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş", "Nevşehir", "Niğde", 
    "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", 
    "Sivas", "Şanlıurfa", "Şırnak", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", 
    "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
]

# Helper function to normalize city names (converting to lower-case and non-turkish characters) for
# adapting a consistent format and avoiding mismatches during database queries
def normalize_city_name(city):
    # Define a translation table from Turkish-specific characters to ASCII equivalents
    turkish_chars = "çğıiöşüâêîûÇĞİÖŞÜÂÊÎÛ"
    english_chars = "cgiiosuaeiucgiosuaeiu"
    translation_table = str.maketrans(turkish_chars, english_chars)
    
    # Apply translation for Turkish characters
    city = city.translate(translation_table)
    
    # Normalize Unicode characters (removes diacritics like â → a)
    city = ''.join(c for c in unicodedata.normalize('NFKD', city) if not unicodedata.combining(c))
    
    # Convert to lower-case and return
    return city.lower()

# Normalize city names in the list
normalized_cities = [normalize_city_name(city) for city in cities]



# ---AIRLINES---

# A simple class to generate airline flight codes for different airlines
class AirlineInfo:
    def __init__(self, name_code):
        # Initialize with the airline's name code and starting flight number (start from 101)
        self.name_code = name_code
        self.flight_number = 101

    def get_next_flight_code(self):
        # Generate the next flight code by combining the airline's name code with the flight number
        flght_code = f"{self.name_code}{self.flight_number}"
        self.flight_number += 1

        # Reset the flight number to 101 if it exceeds 999 (always keep to 3 digits)
        if (self.flight_number > 999):
            self.flight_number = 101

        return flght_code
    
# Dictionary of airlines with their respective AirlineInfo objects
airlines = {"THY" : AirlineInfo("TK"), 
            "Pegasus" : AirlineInfo("PC"), 
            "AJet" : AirlineInfo("AJ"), 
            "SunExpress" : AirlineInfo("SE")}



# ---TIME---

# Generate times for an (arbitrary) day in 15 minute intervals which later
# will be used for assigning departure and arrival times of flights in HH:MM format
def time_generator():
    start = datetime(2025, 3, 15, 0, 0)
    end = datetime(2025, 3, 15, 23, 45)

    current = start
    while current <= end:
        yield current
        current += timedelta(minutes=15)

# Check if a specific time is within busy hour range. When later generating mock flight data,
# %70 percent of the flights will be scheduled during busy hours, and other 30% during remaning quiet hours.
def is_busy_hour(dt):
    # Define busy hour ranges using datetime objects
    # Busy hours are defined as 07:00 - 11:30 and 14:30 - 22:30 in any day
    busy_start_1 = datetime(2025, 3, 15, 7, 0)
    busy_end_1 = datetime(2025, 3, 15, 11, 30)

    busy_start_2 = datetime(2025, 3, 15, 14, 30)
    busy_end_2 = datetime(2025, 3, 15, 22, 30)

    return (busy_start_1 <= dt <= busy_end_1) or (busy_start_2 <= dt <= busy_end_2)

# Helper function to get the arrivel time (in HH:MM format) based on the departure time 
# and flight duration in minutes (e.g. 11:30 + 90 minutes --> 13:00)
def get_arrival_time(departure_time, duration_mins):
    # Parse the departure time string
    hours, minutes = map(int, departure_time.split(":"))

    departure = datetime(2025, 3, 15, hours, minutes)
    arrival = departure + timedelta(minutes=duration_mins)
    
    arrival_time = arrival.strftime("%H:%M")

    return arrival_time

# Create initial empty sets of busy and quiet hours for categorizing flight times
departure_times = {"busy" : set(), "quiet" : set()}

# Iterate over the time generator and populate the busy and quiet hour sets
for dt in time_generator():
    # Get the time string in HH:MM format
    time_str = dt.strftime("%H:%M")

    # Add the time string to the corresponding set
    if is_busy_hour(dt):
        departure_times["busy"].add(time_str)
    else:
        departure_times["quiet"].add(time_str)



# ---DURATION---

# Define a set of possible flight durations in minutes
durations = {70, 75, 80, 90, 95, 105}

# Helper function to convert a duration in minutes to a string in the "Xh Ym" format (e.g. 95 --> '1h 35m')
def get_duration_string(duration_mins):
    hours = duration_mins // 60
    minutes = duration_mins % 60
    return f"{hours}h {minutes}m"



# ---CLASS---

# Define the available flight classes
classes = {"Economy", "Business"}



# ---PRICE---

# Define a set of possible prices for each class
prices = {"Economy" : {1000, 1500, 2000, 2500},
          "Business" : {2000, 3000, 4000, 5000}}



# ---DATE/DAY---

# Generator dunction that defines the date range for the mock flight data
def day_generator():
    # Generate flights starting from 2025-03-15 to 2025-12-31
    start = datetime(2025, 3, 15)
    end = datetime(2025, 12, 31)

    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)