from django.contrib.auth.models import User
from django.db import models

class Chat(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.message}"

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    room_name = models.CharField(max_length=255)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.content[:20]}"
    

class CallSession(models.Model):
    caller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="outgoing_calls")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="incoming_calls")
    sdp_offer = models.TextField(blank=True, null=True)
    sdp_answer = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notified = models.BooleanField(default=False)

class MeetingInvite(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invites")
    target = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_invites")
    room = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    preferred_lang = models.CharField(max_length=10, default="en")

    def __str__(self):
        return f"{self.sender} invited {self.target} to {self.room}"
    
class perform_translation(models.Model):
    print("XXXX")


