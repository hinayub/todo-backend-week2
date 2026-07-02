from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializer import RegisterSerializer
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def csrf_token_view(request):
    """Return a CSRF cookie so the frontend can read it before posting."""
    return JsonResponse({"csrfToken": get_token(request)})

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Log the new user in so a session is established right after signup.
        login(request, user)
        return Response(
            {"message": "Registration successful", "user": serializer.data},
            status=status.HTTP_201_CREATED,
        )

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        # The form logs in with an email; resolve it to a username to authenticate.
        user_obj = User.objects.filter(email=email).first()
        user = authenticate(username=user_obj.username, password=password) if user_obj else None
        if user is not None:
            login(request, user)
            return Response({"message": "Login successful", "user": RegisterSerializer(user).data})
        return Response(
            {"message": "Invalid email or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
