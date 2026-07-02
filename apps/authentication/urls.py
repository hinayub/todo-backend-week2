from django.urls import path
from .views import RegisterView, LoginView, csrf_token_view

urlpatterns = [
    path('csrf/', csrf_token_view, name='csrf-token'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
]