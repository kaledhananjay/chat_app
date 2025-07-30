from pkgutil import get_data
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class MeetingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("MeetingConsumer connect called")
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"meeting_{self.room_name}"
        print(f"🔌 Connecting to room: {self.room_name}")
        
        client_ip, client_port = self.scope["client"]
        print(f"🔌 WebSocket connected from {client_ip}:{client_port} to room: {self.room_name}")

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        await self.send_participant_list()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

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
        
class FallbackConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print(f"⚠️ FallbackConsumer triggered for path: {self.scope['path']}")
        await self.close()



