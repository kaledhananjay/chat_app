from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from chat.models import Message
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .models import CallSession, Chat, MeetingInvite, User,perform_translation
from .serializers import CallOfferSerializer, CallAnswerSerializer
from rest_framework.permissions import IsAuthenticated
from deep_translator import GoogleTranslator
from gtts import gTTS
import speech_recognition as sr
import os
from django.conf import settings
import os, uuid, subprocess
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import cache
import re
from utils.redis_client import redis_client
from utils.tts_cache import get_tts_cached
from rest_framework.decorators import parser_classes
from rest_framework.parsers import MultiPartParser
import whisper
import tempfile

# Example usage
redis_client.set("mykey", "myvalue")
value = redis_client.get("mykey")

@login_required
def chat_list_view(request):
    users = User.objects.exclude(
        id=request.user.id
    )  
    return render(request, "chat_list.html", {"users": users})

@login_required
def chat_view(request, user_id):
    receiver = User.objects.get(id=user_id)
    chat_history = (
        (
            Chat.objects.filter(sender=request.user, receiver=receiver)
            | Chat.objects.filter(sender=receiver, receiver=request.user)
        )
        .order_by("timestamp")
        .reverse()
    )

    if request.method == "POST":
        message = request.POST.get("message")
        
        if message:  
            Chat.objects.create(sender=request.user, receiver=receiver, message=message)
            return redirect("chat", user_id=user_id) 

    users = User.objects.exclude(id=request.user.id)
    return render(
        request,
        "chat.html",
        {"receiver": receiver, "chat_history": chat_history, "users": users},
    )

@csrf_exempt
def loadchat(request):
    receiver_id = request.GET.get("receiver")
    
    if not receiver_id:
        return JsonResponse({"error": "Missing receiver ID"}, status=400)

    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Receiver not found"}, status=404)

    sender = request.user
    if not sender.is_authenticated:
        sender = User.objects.get(username="admin")

    chat_history = Chat.objects.filter(
        sender=sender, receiver=receiver
    ) | Chat.objects.filter(sender=receiver, receiver=sender)

    chat_history = chat_history.order_by("timestamp")

    messages = [
        {
            "sender": msg.sender.username,
            "content": msg.message,
            "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for msg in chat_history
    ]

    return JsonResponse({"messages": messages})

def chat_index(request):
    users = User.objects.exclude(
        username=request.user.username
    ) 
    return render(request, "chat.html", {"users": users})

def chat_page(request):
    receiver_username = request.GET.get("receiver")
    receiver = get_object_or_404(User, username=receiver_username)
    return render(request, "chat.html", {"receiver": receiver})

def get_messages(request, room_name):
    messages = Message.objects.filter(room_name=room_name).order_by("timestamp")
    data = [
        {
            "sender": m.sender.username,
            "content": m.content,
            "timestamp": m.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for m in messages
    ]
    return JsonResponse({"messages": data})

@csrf_exempt
def send_message(request):
    if request.method == "POST":
        data = json.loads(request.body)
        sender = (
            request.user
            if request.user.is_authenticated
            else User.objects.get(username="admin")
        )

        Message.objects.create(
            sender=sender, room_name=data["room_name"], content=data["message"]
        )

        return JsonResponse({"status": "Message Sent!"})
    return JsonResponse({"error": "Invalid request"}, status=400)

@csrf_exempt
@api_view(["POST"])
def start_call(request):
    serializer = CallOfferSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(["GET"])
def get_offer(request):
    try:
        user_id = request.GET.get("for_user")
        if not user_id:
            return Response({"error": "Missing user ID"}, status=status.HTTP_400_BAD_REQUEST)

        call = CallSession.objects.filter(
            receiver_id=user_id,
            sdp_offer__isnull=False,
            sdp_answer__isnull=True,
            is_active=True,
            notified=False,  
        ).last()
        print(f"🔍 Matching calls for user {user_id}: {call}")

        if call is None:
            print(f"ℹ️ No pending call for user {user_id}")
            return Response({"message": "No pending call"}, status=status.HTTP_204_NO_CONTENT)

        call.notified = True
        call.save(update_fields=["notified"])
        print(f"✅ Notifying call ID {call.id} for user {user_id}")
        return Response(CallOfferSerializer(call).data)
    except Exception as e:
        print("Error in get_offer:", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(["POST"])
def send_answer(request):
    try:
        call = CallSession.objects.get(id=request.data["id"])
        serializer = CallAnswerSerializer(call, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "Answer saved"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except CallSession.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)

@csrf_exempt
@api_view(["GET"])
def get_answer(request):
    call_id = request.GET.get("id")
    try:
        call = CallSession.objects.get(id=call_id)
        if call.sdp_answer:
            return Response(CallAnswerSerializer(call).data)
        return Response({"message": "No answer yet"}, status=status.HTTP_204_NO_CONTENT)
    except CallSession.DoesNotExist:
        return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)

@csrf_exempt
@api_view(["POST"])
def test_post(request):
    return Response({"message": "POST received"})

# Returns current logged in user Name and ID
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    print("!!Returns current logged in user Name and ID")
    user = request.user
    return Response(
        {
            "id": user.id,
            "username": user.username,
        }
    )

# Converts source audio to respective text
# Translate source coverted text to target language text
# Converts back target language text to target audio
@csrf_exempt
def translate_audio_from_bytes(audio_bytes, user_id):
    target_lang = cache.get(f"user_lang_{user_id}", "en")
    print("🌐 Target language:", target_lang)

    print("len(audio_bytes):",len(audio_bytes))
    # if len(audio_bytes) < 30000:
    #     print(f"⚠️ Skipping small blob: {len(audio_bytes)} bytes")
    #     return {"translated": "", "audio_url": "", "error": "Blob too small to process"}

    base_filename = str(uuid.uuid4())
    ogg_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.ogg")
    wav_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.wav")
    mp3_path = wav_path.replace(".wav", "_ja.mp3")

    # Save raw bytes to ogg file
    with open(ogg_path, "wb") as f:
        f.write(audio_bytes)
    
    print("🤫 ogg_path:",ogg_path)
    print("🤫 ogg_path size:",os.path.getsize(ogg_path))
    # if os.path.getsize(ogg_path) < 30000:
    #     print("🤫 WebM chunk too small, likely silent or clipped")
    #     return {"translated": "", "audio_url": "", "error": "WebM chunk too small"}

    # Convert to WAV using ffmpeg
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", ogg_path,
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ]
    try:
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0 or not os.path.exists(wav_path):
            raise RuntimeError(result.stderr.decode())
    except Exception as e:
        print("❌ FFmpeg failed:", e)
        return {"translated": "", "audio_url": "", "error": "FFmpeg conversion failed", "details": str(e)}

    # Transcribe
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        print("🗣️ Recognized text:", text)
    except sr.UnknownValueError:
        return {"error": "Speech not understood"}
    except sr.RequestError as e:
        return {"error": f"STT service issue: {e}"}

    # Translate
    try:
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
        print("🌐 Translated text:", translated)
        if not translated.strip():
            return {"translated": "", "audio_url": "", "error": "Translation was empty"}
    except Exception as e:
        return {"error": f"Translation failed: {e}"}

    # TTS
    try:
        tts = gTTS(translated, lang=target_lang)
        tts.save(mp3_path)
        print("🔊 TTS saved:", mp3_path)
    except Exception as e:
        return {"error": f"TTS failed: {e}"}

    audio_url = f"/media/{os.path.basename(mp3_path)}"
    return {"translated": translated, "audio_url": audio_url}

# Converts source audio to respective text
# Translate source coverted text to target language text
# Converts back target language text to target audio
@csrf_exempt
# def translate_audio(request, user_id):
#     user_id = request.POST.get("userId")
#     #user_id = request.data.get("userId")
#     target_lang = cache.get(f"user_lang_{user_id}", "en")  # fallback to English
#     print("Language selected/saved:",target_lang, user_id)
    
#     if request.method != "POST" or "audio" not in request.FILES:
#         return JsonResponse({"error": "Invalid request"}, status=400)

#     audio_file = request.FILES["audio"]
#     print(f"📥 Received blob size: {audio_file.size} bytes")
#     if audio_file.size < 64722:
#             print(f"⚠️ Skipping small blob: {audio_file.size} bytes")
#             return JsonResponse({
#                 "translated": "",
#                 "audio_url": "",
#                 "error": "Blob too small to process"
#             }, status=200)
            
#     base_filename = str(uuid.uuid4())
#     ogg_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.ogg")
#     webm_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.webm")
#     wav_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.wav")

#     if audio_file.size > 3000:
#         with open(ogg_path, "wb") as f:
#             for chunk in audio_file.chunks():
#                 f.write(chunk)

#         ffmpeg_cmd = [
#             "ffmpeg", "-y",
#             "-i", ogg_path,
#             "-acodec", "pcm_s16le",
#             "-ar", "16000",
#             "-ac", "1",
#             wav_path
#         ]
#         print("🎧 FFmpeg conversion complete:", wav_path)
#         print(f"📦 WebM file ogg_path: {ogg_path} bytes")
       
#         ogg_size = os.path.getsize(ogg_path)
#         print(f"📦 WebM file webm_size: {ogg_size} bytes")
#         if ogg_size < 64722:
#             print("🤫 WebM chunk too small, likely silent or clipped")
#             return JsonResponse({
#                 "translated": "",
#                 "audio_url": "",
#                 "error": "WebM chunk too small"
#             }, status=200)
#     try:
#         result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#         if result.returncode != 0 or not os.path.exists(wav_path):
#             raise RuntimeError(result.stderr.decode())
#     except Exception as e:
#             print("❌ FFmpeg failed:", e)
#             return JsonResponse({
#                 "translated": "",
#                 "audio_url": "",
#                 "error": "FFmpeg conversion failed",
#                 "details": str(e)
#             }, status=200)
#     if result.returncode != 0 or not os.path.exists(wav_path):
#         return JsonResponse({
#             "error": "FFmpeg conversion failed",
#             "details": result.stderr.decode(),
#         }, status=500)
#     #    return JsonResponse(
#     #         {
#     #             "error": "FFmpeg conversion failed",
#     #             "details": result.stderr.decode(),
#     #         },
#     #             status=500,
#     #    )

#     recognizer = sr.Recognizer()
#     try:
#         with sr.AudioFile(wav_path) as source:
#             audio = recognizer.record(source)
#         text = recognizer.recognize_google(audio)
#         print("recognizer text:", text)
#     except sr.UnknownValueError:
#         return JsonResponse({"error": "Speech not understood"}, status=422)
#     except sr.RequestError as e:
#         return JsonResponse({"error": f"STT service issue: {e}"}, status=503)

#     try:
#         translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
#         print("🌐 Translated text:", translated)
#         if not translated.strip():
#             return JsonResponse({"error": "Translation empty", "translated": "", "audio_url": ""}, status=200)
#     except Exception as e:
#         return JsonResponse({"error": f"Translation failed: {e}"}, status=500)
#     if not translated.strip():
#         print("⚠️ Empty translation, skipping TTS")
#         return JsonResponse({
#             "translated": "",
#             "audio_url": "",
#             "error": "Translation was empty"
#         }, status=200)
               
#     try:
#         mp3_path = wav_path.replace(".wav", "_ja.mp3")
#         tts = gTTS(translated, lang=target_lang)
#         tts.save(mp3_path)
#         print("translated mp3_path:", mp3_path)
#     except Exception as e:
#         return JsonResponse({"error": f"TTS failed: {e}"}, status=500)

#     audio_url = f"/media/{os.path.basename(mp3_path)}"
#     return JsonResponse({"translated": translated, "audio_url": audio_url})

@csrf_exempt
def set_language(request):
    print("In set_language")
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        data = json.loads(request.body)
        user_id = data.get("userId")
        language = data.get("language")
        print(f"Language set :{language} for user {user_id}")
        
        if not user_id or not language:
            return JsonResponse({"error": "Missing userId or language"}, status=400)

        cache.set(f"user_lang_{user_id}", language, timeout=None)
        return JsonResponse({"status": "ok"})
    except Exception as e:
        print("❌ Error in set_language:", e)
        return JsonResponse({"error": "Server error"}, status=500)


# Saves chat message in database with MesageText, Sender and Receiver
@csrf_exempt
@login_required
def save_message_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            receiver_id = data.get("receiver_id")
            message = data.get("message")

            if not receiver_id or not message:
                return JsonResponse({"error": "Missing receiver or message"}, status=400)

            receiver = User.objects.get(id=receiver_id)
            chat = Chat.objects.create(sender=request.user, receiver=receiver, message=message)

            return JsonResponse({
                "status": "Message saved",
                "message_id": chat.id,
                "timestamp": chat.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

# Fetch meeting room details using room name from database
@login_required
def meeting_room(request, room_name, user_id):
    invited_user = get_object_or_404(User, id=user_id)
    invite = get_object_or_404(MeetingInvite, room=room_name)
    
    return render(request, "meeting.html", {
            "room_name": room_name,
            "username": request.user.username,
            "current_user_id": request.user.id,
            "room_creator_id": invite.sender.id  # ✅ this is the room creator
        })

# Saves meeting room details to database depending on tag which represents the 
# page from which this view is called
@csrf_exempt
@login_required
def send_meeting_invite(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        data = json.loads(request.body)
        room = data.get("room")
        target_id = data.get("target")
        sender = request.user
        tag = data.get("tag")
        if tag == "chat":
            if not room or not target_id:
                return JsonResponse({"error": "Missing room or target"}, status=400)

            User = get_user_model()
            try:
                target_user = User.objects.get(id=target_id)
            except User.DoesNotExist:
                return JsonResponse({"error": "Target user not found"}, status=404)

            # ✅ Save invite to DB
            MeetingInvite.objects.create(sender=sender, target=target_user, room=room)

            print(f"📨 Meeting invite from {sender.username} to {target_user.username} for room {room}")
        elif tag == "meet":
            if not room or not target_id:
                return JsonResponse({"error": "Missing room or target"}, status=400)

            User = get_user_model()
            try:
                target_user = User.objects.get(id=target_id)
            except User.DoesNotExist:
                return JsonResponse({"error": "Target user not found"}, status=404)

            # ✅ Save invite to DB
            #MeetingInvite.objects.create(sender=sender, target=target_user, room=room)

            print(f"📨 Meeting invite from {sender.username} to {target_user.username} for room {room}")
            #✅ Send WebSocket notification to invited user
            channel_layer = get_channel_layer()
            print(f"Sending invite to user_{target_user.id}")
            async_to_sync(channel_layer.group_send)(
                f"user_{target_user.id}",
                {
                    "type": "send_notification",  # ✅ Matches consumer method
                    "payload": {
                        "type": "receive_invite",  # ✅ Matches frontend listener
                        "room": room,
                        "from": sender.username
                    }
                }
            )
            print("Invite sent via Channels")
        return JsonResponse({"status": "invite sent", "room": room})
    except Exception as e:
        print("❌ Error sending invite:", str(e))
        return JsonResponse({"error": str(e)}, status=400)

@login_required
def meeting_room_group(request, room_name):
    all_users = User.objects.exclude(id=request.user.id)
    return render(request, "meeting.html", {
        "room_name": room_name,
        "username": request.user.username,
        "user_id": request.user.id,
        "all_users": all_users,
        "target_user": None,
    })

@login_required
def meeting_room_direct(request, room_name, target_id):
    all_users = User.objects.exclude(id=request.user.id)
    target_user = get_object_or_404(User, id=target_id)
    
    invite = get_object_or_404(MeetingInvite, room=room_name)
    room_creator_id = invite.sender.id

    return render(request, "meeting.html", {
        "room_name": room_name,
        "username": request.user.username,
        "user_id": request.user.id,
        "target_user": target_user,
        "all_users": all_users,
        "room_creator_id": room_creator_id  # ✅ Add this
    })


    # return render(request, "meeting.html", {
    #     "room_name": room_name,
    #     "username": request.user.username,
    #     "user_id": request.user.id,
    #     "target_user": target_user,
    #     "all_users": all_users,
    # })

async def receive(self, text_data):
    data = json.loads(text_data)

    if data["type"] == "join":
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Optionally store user info in memory or DB

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_joined",
                "username": data["user_id"] 
            }
        )
       
async def user_joined(self, event):
    await self.send(text_data=json.dumps({
        "type": "user_joined",
        "username": event["username"]
    }))        
    
def embedded_meeting_view(request, room_name, user_id):
    # Render only the meeting room part
    return render(request, "room_embed.html", {
        "room_name": room_name,
        "user_id": user_id,
    })

@login_required
def get_pending_invites(request):
    user = request.user
    invites = MeetingInvite.objects.filter(target=user, status="pending")
    data = [
        {
            "id": invite.id,
            "sender": invite.sender.username,
            "room": invite.room,
            "timestamp": invite.timestamp.isoformat()
        }
        for invite in invites
    ]
    return JsonResponse({"invites": data})

@csrf_exempt
@login_required
def respond_to_invite(request):
    if request.method == "POST":
        data = json.loads(request.body)
        invite_id = data.get("invite_id")
        action = data.get("action")  # "accept" or "reject"

        try:
            invite = MeetingInvite.objects.get(id=invite_id, target=request.user)
            invite.status = "accepted" if action == "accept" else "rejected"
            invite.save()

            # Optional: Send WebSocket notification to sender
            # channel_layer.group_send(f"user_{invite.sender.id}", {...})

            return JsonResponse({"success": True})
        except MeetingInvite.DoesNotExist:
            return JsonResponse({"error": "Invite not found"}, status=404)

@login_required
def get_meeting_invite_by_room(request, room_name):
    try:
        print("In get_meeting_invite_by_room")
        invite = get_object_or_404(MeetingInvite, room=room_name)

        data = {
            "room": invite.room,
            "sender_id": invite.sender.id,
            "sender_username": invite.sender.username,
            "target_id": invite.target.id,
            "target_username": invite.target.username,
            "timestamp": invite.timestamp.isoformat()
        }
        print("Out get_meeting_invite_by_room")
        return JsonResponse({"status": "ok", "invite": data})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
@login_required
def create_meeting_room(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        room = MeetingInvite.objects.create(created_by=request.user)
        return JsonResponse({"room": room.id})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def temploadchat(request):
    receiver_id = request.GET.get("receiver")
    
    if not receiver_id:
        return JsonResponse({"error": "Missing receiver ID"}, status=400)

    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Receiver not found"}, status=404)

    sender = request.user
    if not sender.is_authenticated:
        sender = User.objects.get(username="admin")

    chat_history = Chat.objects.filter(
        sender=sender, receiver=receiver
    ) | Chat.objects.filter(sender=receiver, receiver=sender)

    chat_history = chat_history.order_by("timestamp")

    messages = [
        {
            "sender": msg.sender.username,
            "content": msg.message,
            "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for msg in chat_history
    ]

    return JsonResponse({"messages": messages})

# translate_audio_realtime (Text-to-Speech (TTS))
# Save the output translated audio file path by Caching
@csrf_exempt
def translate_audio_realtime(request):
    try:
        if request.method != "POST" or "audio" not in request.FILES:
            return JsonResponse({"error": "Invalid request"}, status=400)

        audio_file = request.FILES["audio"]
        print(f"📥 Received blob size: {audio_file.size} bytes")
        if audio_file.size == 64722:
            print(f"⚠️ Skipping small blob: {audio_file.size} bytes")
            return JsonResponse({
                "translated": "",
                "audio_url": "",
                "error": "Blob too small to process"
            }, status=200)


        user_id = request.POST.get("senderId")
        target_lang = request.POST.get("targetLang")
        
        base_filename = str(uuid.uuid4())
        webm_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.webm")
        wav_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.wav")

        if audio_file.size > 3000:  # ~3KB
            with open(webm_path, "wb") as f:
                for chunk in audio_file.chunks():
                    f.write(chunk)

            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", webm_path,
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                wav_path
            ]
            print("🎧 FFmpeg conversion complete:", wav_path)
            print(f"📦 WebM file webm_path: {webm_path} bytes")
            webm_size = os.path.getsize(webm_path)
            print(f"📦 WebM file size: {webm_size} bytes")
            if webm_size == 64722:
                print("🤫 WebM chunk too small, likely silent or clipped")
                return JsonResponse({
                    "translated": "",
                    "audio_url": "",
                    "error": "WebM chunk too small"
                }, status=200)
        try:
            result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0 or not os.path.exists(wav_path):
                raise RuntimeError(result.stderr.decode())
        except Exception as e:
            #print("❌ FFmpeg failed:", e)
            return JsonResponse({
                "translated": "",
                "audio_url": "",
                "error": "FFmpeg conversion failed",
                "details": str(e)
            }, status=200)

        if result.returncode != 0 or not os.path.exists(wav_path):
            return JsonResponse({
                "error": "FFmpeg conversion failed",
                "details": result.stderr.decode(),
            }, status=500)

        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return JsonResponse({"error": "Speech not understood"}, status=422)
        except Exception as e:
            return JsonResponse({"error": f"STT failed: {e}"}, status=500)

        try:
            translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
            print("🌐 Translated text:", translated)
            if not translated.strip():
                return JsonResponse({"error": "Translation empty", "translated": "", "audio_url": ""}, status=200)
        except Exception as e:
                return JsonResponse({"error": f"Translation failed: {e}"}, status=500)

        if not translated.strip():
            print("⚠️ Empty translation, skipping TTS")
            return JsonResponse({
                "translated": "",
                "audio_url": "",
                "error": "Translation was empty"
            }, status=200)
        try:
            mp3_path = get_tts_cached(translated, target_lang)
            audio_url = f"/media/{os.path.basename(mp3_path)}"
            print("📁 Final MP3 path:", mp3_path)
            print("📦 Exists:", os.path.exists(mp3_path))
            # mp3_path = wav_path.replace(".wav", f"_{target_lang}.mp3")
            # tts = gTTS(translated, lang=target_lang)
            # tts.save(mp3_path)
            # print("🔊 TTS audio saved:", mp3_path)

        except Exception as e:
            print("❌ TTS failed:", e)
            return JsonResponse({
                "translated": translated,
                "audio_url": "",
                "error": "TTS synthesis failed",
                "details": str(e)
            }, status=200)
            
        return JsonResponse({"translated": translated, "audio_url": audio_url})
    except Exception as e:
        print("🔥 Unexpected error:", e)
        return JsonResponse({
            "translated": "",
            "audio_url": "",
            "error": "Unexpected server error",
            "details": str(e)
        }, status=200)

async def send_translated_audio(self, sender_id, audio_url, translated_text, target_lang):
    await self.channel_layer.group_send(
        "meeting_room",  # or use dynamic room name
        {
            "type": "translated.audio",
            "senderId": sender_id,
            "audio_url": audio_url,
            "translated_text": translated_text,
            "target_lang": target_lang
        }
    )
    
@csrf_exempt
def set_language(request):
    print("In set_language")

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        raw_body = request.body.decode("utf-8")  # ✅ decode bytes to string
        print("📥 Raw body:", raw_body)

        data = json.loads(raw_body)  # ✅ now safe to parse
        user_id = data.get("userId")
        language = data.get("language")

        print(f"🌍 Language set: {language} for user {user_id}")

        if not user_id or not language or user_id == "null":
            return JsonResponse({"error": "Missing or invalid userId or language"}, status=400)

        cache.set(f"user_lang_{user_id}", language, timeout=None)
        return JsonResponse({"status": "ok"})

    except json.JSONDecodeError as e:
        print("❌ JSON decode error:", e)
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    except Exception as e:
        print("❌ General error in set_language:", e)
        return JsonResponse({"error": "Server error"}, status=500)


    
def get_preferred_language(request):
    user_id = request.GET.get("userId")
    room = request.GET.get("room")

    try:
        invite = MeetingInvite.objects.get(target_id=user_id, room=room)
        return JsonResponse({"preferred_lang": invite.preferred_lang})
    except MeetingInvite.DoesNotExist:
        return JsonResponse({"error": "Invite not found"}, status=404)

