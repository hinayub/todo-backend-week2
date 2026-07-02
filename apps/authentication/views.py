from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from rest_framework import APIView, Response, generics, permissions, status

from .serializer import RegisterSerializer

# Create your views here.


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return Response(
                {"message": "Login successful", "user": RegisterSerializer(user).data}
            )
        else:
            return Response(
                {"message": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )
