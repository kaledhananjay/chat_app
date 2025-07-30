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
from .models import CallSession, Chat, MeetingInvite
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
        
        print('I am here to save message :::: ', message)
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
        print("Returning messages for room:", data["room_name"])
        print(Message.objects.filter(room_name=data["room_name"]))

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
        print("🔍 Incoming offer request for user:", user_id)

        call = CallSession.objects.filter(
            receiver_id=user_id,
            sdp_offer__isnull=False,
            sdp_answer__isnull=True,
            is_active=True,
            notified=False,  
        ).last()

        if call:
            call.notified = True  
            call.save()
            return Response(CallOfferSerializer(call).data)

        return Response(
            {"message": "No pending call"}, status=status.HTTP_204_NO_CONTENT
        )

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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    user = request.user
    return Response(
        {
            "id": user.id,
            "username": user.username,
        }
    )

@csrf_exempt
def translate_audio(request):
    if request.method != "POST" or "audio" not in request.FILES:
        return JsonResponse({"error": "Invalid request"}, status=400)

    audio_file = request.FILES["audio"]
    base_filename = str(uuid.uuid4())
    ogg_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.ogg")
    wav_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.wav")

    with open(ogg_path, "wb") as f:
        for chunk in audio_file.chunks():
            f.write(chunk)

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", ogg_path,
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ]

    result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
       return JsonResponse(
            {
                "error": "FFmpeg conversion failed",
                "details": result.stderr.decode(),
            },
                status=500,
       )

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return JsonResponse({"error": "Speech not understood"}, status=422)
    except sr.RequestError as e:
        return JsonResponse({"error": f"STT service issue: {e}"}, status=503)

    try:
        translated = GoogleTranslator(source="auto", target="ja").translate(text)
    except Exception as e:
        return JsonResponse({"error": f"Translation failed: {e}"}, status=500)
       
    try:
        mp3_path = wav_path.replace(".wav", "_ja.mp3")
        print("🔉Japanese TTS : ", mp3_path)
        tts = gTTS(translated, lang="ja")
        tts.save(mp3_path)
        print("TTS audio saved:", mp3_path)
    except Exception as e:
        return JsonResponse({"error": f"TTS failed: {e}"}, status=500)

    audio_url = f"/media/{os.path.basename(mp3_path)}"
    return JsonResponse({"translated": translated, "audio_url": audio_url})

@csrf_exempt
@login_required
def save_message_view(request):
    if request.method == "POST":
        try:
            print("Raw body:", request.body)
            data = json.loads(request.body)
            print("Parsed data:", data)

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

@login_required
def meeting_room(request, room_name, user_id):
    invited_user = get_object_or_404(User, id=user_id)
    return render(request, "meeting.html", {
        "room_name": room_name,
        "username": invited_user.username 
    })

@csrf_exempt  # Optional: remove if using CSRF tokens
@login_required
def send_meeting_invite(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            room = data.get("room")
            target_id = data.get("target")
            sender = request.user

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

            return JsonResponse({"status": "invite sent", "room": room})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)




        
@login_required
def meeting_room_group(request, room_name):
    print("🔥 meeting_room_group triggered")
    all_users = User.objects.exclude(id=request.user.id)
    print("✅ all_users:", list(all_users))
    return render(request, "meeting.html", {
        "room_name": room_name,
        "username": request.user.username,
        "user_id": request.user.id,
        "all_users": all_users,
        "target_user": None,
    })

@login_required
def meeting_room_direct(request, room_name, target_id):
    print("🔥 meeting_room_direct triggered")
    all_users = User.objects.exclude(id=request.user.id)
    target_user = get_object_or_404(User, id=target_id)
    return render(request, "meeting.html", {
        "room_name": room_name,
        "username": request.user.username,
        "user_id": request.user.id,
        "target_user": target_user,
        "all_users": all_users,
    })

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