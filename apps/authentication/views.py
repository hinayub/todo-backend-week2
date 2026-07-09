from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializer import RegisterSerializer

REFRESH_COOKIE_NAME = settings.REFRESH_COOKIE_NAME


def set_refresh_cookie(response, refresh_token):
    """Attach the refresh token to the response as an httpOnly cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=str(refresh_token),
        httponly=True,      # JS can't read this cookie -> mitigates XSS token theft
        secure=False,       # set True once you're serving over HTTPS
        samesite="Lax",     # blocks the cookie from being sent on cross-site requests
        path="/api/auth/",  # only sent to auth endpoints, not every request
    )


def issue_tokens_response(user, data, status_code):
    """Build the JSON response body + set the refresh cookie for a given user."""
    refresh = RefreshToken.for_user(user)
    response = Response(
        {"access": str(refresh.access_token), **data},
        status=status_code,
    )
    set_refresh_cookie(response, refresh)
    return response


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return issue_tokens_response(
            user,
            {"message": "Registration successful", "user": serializer.data},
            status.HTTP_201_CREATED,
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
            return issue_tokens_response(
                user,
                {"message": "Login successful", "user": RegisterSerializer(user).data},
                status.HTTP_200_OK,
            )
        return Response(
            {"message": "Invalid email or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if raw_token is None:
            return Response({"message": "No refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(raw_token)
        except TokenError:
            return Response({"message": "Invalid or expired refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        access = str(refresh.access_token)
        response = Response({"access": access}, status=status.HTTP_200_OK)

        # ROTATE_REFRESH_TOKENS=True means this old refresh token is now blacklisted
        # (BLACKLIST_AFTER_ROTATION=True) and we must hand back a brand new one.
        refresh.blacklist()
        new_refresh = RefreshToken.for_user(User.objects.get(id=refresh["user_id"]))
        set_refresh_cookie(response, new_refresh)
        return response


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(RegisterSerializer(request.user).data)


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if raw_token:
            try:
                RefreshToken(raw_token).blacklist()
            except TokenError:
                pass  # already invalid/expired -- nothing to revoke

        response = Response({"message": "Logged out"}, status=status.HTTP_200_OK)
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/auth/")
        return response
