from django.urls import path
from .views import (
    get_messages, send_message, chat_list_view, chat_view, loadchat,
    current_user_view, save_message_view,
    meeting_room_group, meeting_room_direct,
    start_call, get_offer, send_answer, get_answer,
    test_post, translate_audio,send_meeting_invite,embedded_meeting_view,
    get_pending_invites, respond_to_invite,get_meeting_invite_by_room,create_meeting_room
)

urlpatterns = [
    # Chat APIs
    path('api/chat/messages/<str:room_name>/', get_messages, name='get_messages'),
    path('api/chat/send/', send_message, name='send_message'),
    path("chat/", chat_list_view, name="chat_list"),
    path("chat/<int:user_id>/", chat_view, name="chat"),
    path("chat/load/", loadchat, name="chat_view"),
    path("api/chat/save/", save_message_view, name="save_message"),

    # User & Audio APIs
    path('api/me', current_user_view),
    path('translate-audio/', translate_audio, name='translate_audio'),

    # Call APIs
    path('api/call/start', start_call),
    path('api/call/offer', get_offer),
    path('api/call/answer', send_answer),
    path('api/call/response', get_answer),

    # Misc
    path('api/test-post', test_post),

    # ✅ Correct Meeting Views
    path("meeting/<str:room_name>/", meeting_room_group, name="meeting_group"),
    path("meeting/<str:room_name>/<int:target_id>/", meeting_room_direct, name="meeting_direct"),
    path("api/send-meeting-invite/", send_meeting_invite, name="send_meeting_invite"),
    path('meeting/embed/<str:room_name>/<int:user_id>/', embedded_meeting_view, name='embedded_meeting'),
    path("api/invites/pending/", get_pending_invites, name="get_pending_invites"),
    path("api/invites/respond/", respond_to_invite, name="respond_to_invite"),
    path("api/invite/<str:room_name>/", get_meeting_invite_by_room, name="get_meeting_invite_by_room"),
    path('api/create-meeting-room', create_meeting_room, name='create_meeting_room'),
]