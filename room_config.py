# Room configuration for multi-room smart home system
# Each room contains multiple sensors

ROOMS = {
    "Living Room": {
        "room_id": 1,
        "sensors": {
            "temperature": "pr/home/room1/temperature",
            "humidity": "pr/home/room1/humidity",
            "light": "pr/home/room1/light"
        }
    },
    "Bedroom": {
        "room_id": 2,
        "sensors": {
            "temperature": "pr/home/room2/temperature",
            "humidity": "pr/home/room2/humidity",
            "light": "pr/home/room2/light"
        }
    },
    "Kitchen": {
        "room_id": 3,
        "sensors": {
            "temperature": "pr/home/room3/temperature",
            "humidity": "pr/home/room3/humidity",
            "light": "pr/home/room3/light"
        }
    },
    "Bathroom": {
        "room_id": 4,
        "sensors": {
            "temperature": "pr/home/room4/temperature",
            "humidity": "pr/home/room4/humidity",
            "light": "pr/home/room4/light"
        }
    },
    "Office": {
        "room_id": 5,
        "sensors": {
            "temperature": "pr/home/room5/temperature",
            "humidity": "pr/home/room5/humidity",
            "light": "pr/home/room5/light"
        }
    },
    "Garage": {
        "room_id": 6,
        "sensors": {
            "temperature": "pr/home/room6/temperature",
            "humidity": "pr/home/room6/humidity",
            "light": "pr/home/room6/light"
        }
    }
}

# CUSTOM TOPIC MAPPING - Add any non-standard topics here
# Format: "full_topic_path": ("room_name", "sensor_type")
# Example: "home/device1/humidity": ("Living Room", "humidity")
CUSTOM_TOPIC_MAP = {
    # Map your actual sensor topics here
    "pr/home/5976397/sts": ("Living Room", "humidity"),
    "pr/home/room1/humidity": ("Living Room", "humidity"),
    "pr/home/room2/humidity": ("Bedroom", "humidity"),
    # Add more custom mappings below:
    # "pr/home/relay_123_YY/temperature": ("Kitchen", "temperature"),
}

# Get room names list
def get_room_names():
    return list(ROOMS.keys())

# Get all topics from all rooms
def get_all_topics():
    topics = []
    for room_name, room_data in ROOMS.items():
        for sensor_name, topic in room_data["sensors"].items():
            topics.append(topic)
    return topics

# Get room name from topic
def get_room_from_topic(topic):
    # First check custom topic map
    if topic in CUSTOM_TOPIC_MAP:
        return CUSTOM_TOPIC_MAP[topic][0]
    
    # Then check standard format
    for room_name, room_data in ROOMS.items():
        for sensor_name, sensor_topic in room_data["sensors"].items():
            if sensor_topic == topic:
                return room_name
    return None

# Get sensor type from topic
def get_sensor_type_from_topic(topic):
    # First check custom topic map
    if topic in CUSTOM_TOPIC_MAP:
        return CUSTOM_TOPIC_MAP[topic][1]
    
    # Then check standard format
    for room_name, room_data in ROOMS.items():
        for sensor_name, sensor_topic in room_data["sensors"].items():
            if sensor_topic == topic:
                return sensor_name
    return None
