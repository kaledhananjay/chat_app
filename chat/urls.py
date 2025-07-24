from django.urls import path
from .views import get_messages, send_message,chat_list_view,chat_view,loadchat,current_user_view,save_message_view
from . import views

urlpatterns = [
    path('api/chat/messages/<str:room_name>/', get_messages, name='get_messages'),
    path('api/chat/send/', send_message, name='send_message'),
    path("chat/", chat_list_view, name="chat_list"),  # Shows all users
    path("chat/<int:user_id>/", chat_view, name="chat"),  # Requires user_ids
    path("api/chat/send/", send_message, name="send_message"),
    path("chat/load/", loadchat, name="chat_view"),
    path('api/call/start', views.start_call),
    path('api/call/offer', views.get_offer),
    path('api/call/answer', views.send_answer),
    path('api/call/response', views.get_answer),
    path('api/test-post', views.test_post),
    path('api/me', current_user_view),
    path('translate-audio/', views.translate_audio, name='translate_audio'),
    path("api/chat/save/", save_message_view, name="save_message"),
    path("meeting/<str:room_name>/", views.meeting_room, name="meeting_room"),
    path("api/send-meeting-invite/", views.send_meeting_invite, name="send_meeting_invite"),



]