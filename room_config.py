
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


CUSTOM_TOPIC_MAP = {
    "pr/home/5976397/sts": ("Living Room", "humidity"),
    "pr/home/room1/humidity": ("Living Room", "humidity"),
    "pr/home/room2/humidity": ("Bedroom", "humidity"),
}

def get_room_names():
    return list(ROOMS.keys())


def get_all_topics():
    topics = []
    for room_name, room_data in ROOMS.items():
        for sensor_name, topic in room_data["sensors"].items():
            topics.append(topic)
    return topics


def get_room_from_topic(topic):
  
    if topic in CUSTOM_TOPIC_MAP:
        return CUSTOM_TOPIC_MAP[topic][0]
    
  
    for room_name, room_data in ROOMS.items():
        for sensor_name, sensor_topic in room_data["sensors"].items():
            if sensor_topic == topic:
                return room_name
    return None

def get_sensor_type_from_topic(topic):
    
    if topic in CUSTOM_TOPIC_MAP:
        return CUSTOM_TOPIC_MAP[topic][1]
    
    
    for room_name, room_data in ROOMS.items():
        for sensor_name, sensor_topic in room_data["sensors"].items():
            if sensor_topic == topic:
                return sensor_name
    return None
