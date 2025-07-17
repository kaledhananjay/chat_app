# import json
# from channels.generic.websocket import AsyncWebsocketConsumer
# import logging
# logger = logging.getLogger(__name__)

# class ChatConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         kwargs = self.scope.get("url_route", {}).get("kwargs", {})

#         if not isinstance(kwargs, dict):
#             print("❌ ERROR: Expected kwargs to be dict, found:", type(kwargs))
#             await self.close()
#             return

#         user_id = kwargs.get("user_id")
#         if not user_id:
#             print("❌ ERROR: user_id missing")
#             await self.close()
#             return

#         self.room_name = f"chat_{user_id}"
#         self.room_group_name = f"group_{self.room_name}"

#         await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#         await self.accept()


#         #self.user_id = self.scope["url_route"]["kwargs"].get("user_id")

#         # print("DEBUG: self.scope['url_route']['kwargs'] =", self.scope['url_route']['kwargs'])  
#         # print("DEBUG: Type of kwargs =", type(self.scope['url_route']['kwargs']))  
#         # if not self.user_id:
#         #     await self.close()
#         #     return
        
#         #self.room_name = f"chat_{self.user_id}"
#         # self.room_name = f"chat_{self.scope['url_route']['kwargs'][0]}"  # ✅ Use numeric index instead of key
#         # self.room_group_name = f"group_{self.room_name}"

#         # await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#         # await self.accept()  # ✅ Accept WebSocket connection

#         # Notify others that user joined
#         # await self.channel_layer.group_send(
#         #     self.room_group_name,
#         #     {"type": "chat_message", "message": f"User {self.user_id} joined the chat"}
#         # )

#     async def disconnect(self, close_code):
#         print("disconnect--------------------------------------------------------------------------------------------")
#         await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

#     async def receive(self, text_data):
#         print("receive--------------------------------------------------------------------------------------------")
#         data = json.loads(text_data)
#         message = data.get("message", "")

#         await self.channel_layer.group_send(
#             self.room_group_name,
#             {"type": "chat_message", "message": message}
#         )

#     async def chat_message(self, event):
#         await self.send(text_data=json.dumps(event))  # ✅ Sends message to the client