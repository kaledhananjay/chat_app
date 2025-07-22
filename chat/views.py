from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Chat
from chat.models import Message
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .models import CallSession, Chat
from .serializers import CallOfferSerializer, CallAnswerSerializer
from rest_framework.permissions import IsAuthenticated
from deep_translator import GoogleTranslator
from gtts import gTTS
import speech_recognition as sr
import os
#import tempfile
#from pydub import AudioSegment
from django.conf import settings
import os, uuid, subprocess
from django.shortcuts import get_object_or_404
#from django.http import JsonResponse
#from django.views.decorators.csrf import csrf_exempt
#from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
#from django.contrib.auth.models import User
#from .models import 
#import json



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

    #Step 1: Save incoming .webm blob
    audio_file = request.FILES["audio"]
    base_filename = str(uuid.uuid4())
    ogg_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.ogg")
    wav_path = os.path.join(settings.MEDIA_ROOT, f"{base_filename}.wav")

    #Save OGG file
    with open(ogg_path, "wb") as f:
        for chunk in audio_file.chunks():
            f.write(chunk)

    #Step 2: Convert WebM → WAV via FFmpeg
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

    #Step 3: Transcribe speech with Google STT
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return JsonResponse({"error": "Speech not understood"}, status=422)
    except sr.RequestError as e:
        return JsonResponse({"error": f"STT service issue: {e}"}, status=503)

    # Step 4: Translate text to Japanese
    try:
        translated = GoogleTranslator(source="auto", target="ja").translate(text)
    except Exception as e:
        return JsonResponse({"error": f"Translation failed: {e}"}, status=500)
        
       
    # Step 5: Generate Japanese TTS
    try:
        mp3_path = wav_path.replace(".wav", "_ja.mp3")
        print("🔉Japanese TTS : ", mp3_path)
        tts = gTTS(translated, lang="ja")
        tts.save(mp3_path)
        print("TTS audio saved:", mp3_path)
    except Exception as e:
        return JsonResponse({"error": f"TTS failed: {e}"}, status=500)

    # Step 6: Return audio URL
    audio_url = f"/media/{os.path.basename(mp3_path)}"
    return JsonResponse({"translated": translated, "audio_url": audio_url})


#@method_decorator(csrf_exempt, name='dispatch')
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