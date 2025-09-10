from pkgutil import get_data
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from django.core.cache import cache
from channels.generic.websocket import AsyncJsonWebsocketConsumer

# Global in-memory store for participants per room
ROOM_PARTICIPANTS = {}

class MeetingConsumer(AsyncJsonWebsocketConsumer):
#class MeetingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:     
            print("🧠 MeetingConsumer connected for:", self.scope["path"])
            self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
            self.user = self.scope["user"]
            self.user_group = f"user_{self.user.id}"
            self.room_group_name = f"chat_{self.room_name}"
            if self.user.is_anonymous:
                await self.close()
                return
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
        except Exception as e:
            print("❌ Exception in connect:", str(e))


    # async def receive(self, text_data):
    #     print("📩 Raw message received:", text_data)
    
    async def disconnect(self, close_code):
        try:
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
        except Exception as e:
            print(f"🔌 WebSocket disconnected with code {close_code}")



    async def voice_joined(self, event):
        #user_id = event["userId"]
        print("📤 Sending voice_joined with userId:", event["userId"])

        await self.send(text_data=json.dumps({
            "type": "voice_joined",
            "userId": event["userId"]
        }))

    async def participant_update(self, event):
        await self.send_participant_list()

    async def send_participant_list(self):
        participants = get_participants(self.room_name)
        await self.send(text_data=json.dumps({
            "type": "participant.update",
            "participants": participants
        }))

    async def mic_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "mic.status",
            "user_id": event["user_id"],
            "mic_on": event["mic_on"],
            "username": event["username"],
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

    async def voice_offer(self, event):
        print("📤 Sending voice.offer to frontend:", event)

        await self.send(text_data=json.dumps({
            "type": "voice.offer",
            "from": event["from"],
            "to": event["to"],
            "sdp": event["sdp"]
        }))
                
    async def receive_json(self, content):
        try:
            print("📨 Incoming WebSocket message:", content)
            msg_type = content["type"]
            print("📥 receive_json called with:", content)
            print("📥 content['type'] =", content.get("type"))
            if msg_type == "voice.ready" or msg_type == "join":
                user_id = self.scope["user"].id
                #print("📡 voice.ready received from:", user_id)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "voice_joined",
                        "userId": user_id
                    }
                )
            elif msg_type == "voice.offer":
                try:
                    print("📡 Backend received voice.offer from", content["sender"], content["target"], content["sdp"])
                    target_id = content["target"]
                    sdp = content["sdp"]
                    sender = content["sender"]
                    if not target_id or not sdp:
                        raise ValueError("Missing target or SDP")
                    
                    print("📤 Preparing to send offer:", {
                        "from": sender,
                        "to": target_id,
                        "sdp_length": len(sdp)
                    })

                    await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "voice_offer", 
                        "from":sender,
                        "to": target_id,
                        "sdp":sdp
                    }
                )
                except Exception as e:
                    print("❌ Error handling voice.offer:", str(e))
                    await self.close(code=1011)


            elif msg_type  == "voice.answer":
                await self.channel_layer.group_send(
                    f"user_{content["to"]}",
                    {
                        "type": "voice_answer",
                        "from": content["from"],
                        "sdp": content["sdp"]
                    }
                )
            elif msg_type  == "voice.ice":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "voice_ice",  # This must match the method name above
                        # "from": content["from"],
                        # "to": content["to"],
                        "from": content.get("from") or content.get("sender"),
                        "to": content.get("to") or content.get("target"),
                        "candidate": content["candidate"]
                    }
                )
            elif msg_type   == "voice.ready":
                user_id = self.scope["user"].id
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "voice_joined",
                        "userId": user_id
                    }
                )
        except Exception as e:
            print("❌ Exception in receive_json:", str(e))
            await self.close(code=1011)
       

    async def voice_answer(self, event):
        await self.send(text_data=json.dumps({
            "type": "voice.answer",
            "from": event["from"],
            "sdp": event["sdp"]
        }))

    async def voice_ice(self, event):
        await self.send(text_data=json.dumps({
            "type": "voice.ice",
            "from": event["from"],
            "to": event["to"],
            "candidate": event["candidate"]
        }))
        
class FallbackConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print(f"⚠️ FallbackConsumer triggered for path: {self.scope['path']}")
        await self.close()

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
            await self.accept()
            print(f"✅ User {self.scope['user'].id} joined group user_{self.scope['user'].id}")
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
    
