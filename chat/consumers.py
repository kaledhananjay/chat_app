from pkgutil import get_data
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from django.core.cache import cache

# Global in-memory store for participants per room
ROOM_PARTICIPANTS = {}



class MeetingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.user = self.scope["user"]
        self.user_group = f"user_{self.user.id}"
        self.room_group_name = f"chat_{self.room_name}"
        print("Position 1.")
        if self.user.is_anonymous:
            await self.close()
            return
        print("Position 2.")
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"✅ Connected: {self.user.username} added to {self.user_group} in room {self.room_name}")
        
        # Add user to Redis-backed participant list
        add_participant(self.room_name, self.user)

        # Broadcast updated list to all users in room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "participant_update"
            }
        )
        await self.send_participant_list()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Remove user from Redis-backed list
        remove_participant(self.room_name, self.user.id)

        # Broadcast updated list
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "participant_update"
            }
        )

            # # Remove user from participant list
            # ROOM_PARTICIPANTS[self.room_name] = [
            #     p for p in ROOM_PARTICIPANTS[self.room_name]
            #     if p["id"] != self.user.id
            # ]

            # # Broadcast updated list
            # await self.channel_layer.group_send(
            #     self.room_group_name,
            #     {
            #         "type": "participant_update"
            #     }
            # )

    async def participant_update(self, event):
        await self.send_participant_list()


    async def send_participant_list(self):
        participants = get_participants(self.room_name)
        await self.send(text_data=json.dumps({
            "type": "participant.update",
            "participants": participants
        }))




    async def receive(self, text_data):
        print("🔍 Incoming WebSocket message:", text_data)
        data = json.loads(text_data)
        
        msg_type = data.get("type")
        if data["type"] == "join":
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            # ✅ Broadcast a transformed message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_joined",
                    "username": data.get("user_id", "anonymous")
                }
            )
        elif msg_type == "invite":
            print("MeetingConsumer-receive ", msg_type)
            target_user_id = data["target_user_id"]
            room = data["room"]
            sender = self.scope["user"].username

            await self.channel_layer.group_send(
                f"user_{target_user_id}",
                {
                    "type": "receive_invite",
                    "room": room,
                    "from": sender
                }
            )
            print(f"📤 Sent invite to user_{target_user_id} for room {room}")
        else:
            # ✅ Forward other messages (e.g., chat, signal)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "signal_message",
                    "message": text_data
                }
            )
        if data["type"] == "mic.status":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "mic_status",
                    "user_id": data["user_id"],
                    "mic_on": data["mic_on"],
                    "username": self.scope["user"].username,
                }
            )
        if not hasattr(self, "room_group_name"):
            print("⚠️ Tried to send before joining a room")
            return
            
    async def mic_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "mic.status",
            "user_id": event["user_id"],
            "mic_on": event["mic_on"],
            "username": event["username"],
        }))

    async def send_participant_list(self):
        participants = [
            {"id": self.scope["user"].id, "username": self.scope["user"].username, "mic_on": False}
        ]
        await self.send(text_data=json.dumps({
            "type": "participant.update",
            "participants": participants
        }))
    
    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_joined",
            "username": event["username"]
        }))
        
    async def signal_message(self, event):
        await self.send(text_data=event["message"])
        
    async def send_meeting_invite(self, event):
        await self.send(text_data=json.dumps({
            "type": "meeting_invite",
            "room": event["room"],
            "sender": event["sender"]
    }))

    async def signal_message(self, event):
        await self.send(text_data=event["message"])
    
    async def receive_invite(self, event):
        print(f"📨 Received invite event-consumer: {event}") 
        await self.send(text_data=json.dumps({
            "type": "receive_invite",
            "room": event["room"],
            "from": event["from"]
        }))
        
class FallbackConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        #print(f"⚠️ FallbackConsumer triggered for path: {self.scope['path']}")
        await self.close()
        
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
            await self.accept()
            print(f"✅ NotificationConsumer connected for user_{self.user.id}")
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)

    async def receive_invite(self, event):
        await self.send(text_data=json.dumps({
            "type": "receive_invite",
            "room": event["room"],
            "from": event["from"]
        }))
        
    async def send_notification(self, event):
        print(f"📨 Sending to {self.user.username}: {event['payload']}")
        await self.send(text_data=json.dumps(event["payload"]))   
        
    async def voice_offer(self, event):
        await self.send(text_data=json.dumps({
            "type": "voice.offer",
            "from": event["from"],
            "sdp": event["sdp"]
        }))



 
        


def get_participants(room_name):
    return cache.get(f"participants:{room_name}", [])

def set_participants(room_name, participants):
    cache.set(f"participants:{room_name}", participants, timeout=None)

def add_participant(room_name, user):
    participants = get_participants(room_name)
    if not any(p["id"] == user.id for p in participants):
        participants.append({
            "id": user.id,
            "username": user.username,
            "mic_on": False
        })
        set_participants(room_name, participants)

def remove_participant(room_name, user_id):
    participants = get_participants(room_name)
    participants = [p for p in participants if p["id"] != user_id]
    set_participants(room_name, participants)
    
async def receive_json(self, content):
    if content["type"] == "voice.ready":
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "voice_joined",
                "userId": content["userId"]
            }
        )
    if content["type"] == "voice.offer":
        await self.channel_layer.group_send(
            f"user_{content["to"]}",
            {
                "type": "voice_offer",
                "from": content["from"],
                "sdp": content["sdp"]
            }
        ) 