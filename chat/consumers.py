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

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "signal_message",
                    "message": text_data
                }
            )
        
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

