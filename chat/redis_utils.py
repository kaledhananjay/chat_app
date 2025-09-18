import redis

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

def add_participant(room_name, user):
    key = f"room:{room_name}:participants"
    redis_client.sadd(key, user.username)