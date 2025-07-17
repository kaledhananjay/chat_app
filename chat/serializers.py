# chat/serializers.py
from rest_framework import serializers
from .models import CallSession

class CallOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSession
        fields = ['id', 'caller', 'receiver', 'sdp_offer']

class CallAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSession
        fields = ['id', 'sdp_answer']