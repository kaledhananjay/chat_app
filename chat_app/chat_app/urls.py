"""
URL configuration for chat_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os
from django.contrib import admin
from django.urls import path, include
from chat.views import chat_page
from django.conf import settings
from django.conf.urls.static import static
from chat.views import translate_audio
from chat_app.settings import BASE_DIR  

urlpatterns = [
    path('admin/', admin.site.urls),
    path("chat/", include("chat.urls")),
    path("auth/", include("users.urls")),  # Include user authentication routes
    path('', include('chat.urls')),  # or whatever your app is called
    path('translate-audio/', translate_audio, name='translate_audio'),
    path("", include("chat.urls")),  # or "users.urls" depending on where you put the view
]

urlpatterns += static(settings.STATIC_URL, document_root=os.path.join(BASE_DIR, 'static'))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
