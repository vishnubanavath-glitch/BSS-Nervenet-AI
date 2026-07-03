from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import serializers
from conversation.models.wallet import Wallet

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(write_only=True, required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False

    def validate(self, attrs):
        email = attrs.get("email")
        username = attrs.get("username")
        
        if email:
            attrs["username"] = email
        elif username:
            attrs["username"] = username
            
        data = super().validate(attrs)
        # Rename keys for frontend compatibility
        data["access_token"] = data.pop("access")
        data["refresh_token"] = data.pop("refresh")
        return data

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer

class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    refresh_token = serializers.CharField(write_only=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["refresh"].required = False

    def validate(self, attrs):
        refresh_token = self.initial_data.get("refresh_token")
        if refresh_token:
            attrs["refresh"] = refresh_token
            
        data = super().validate(attrs)
        data["access_token"] = data.pop("access")
        if "refresh" in data:
            data["refresh_token"] = data.pop("refresh")
        else:
            data["refresh_token"] = refresh_token
        return data

class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    email = request.data.get("email")
    password = request.data.get("password")
    full_name = request.data.get("full_name", "")

    if not email or not password:
        return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({"detail": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

    username = email
    
    try:
        first_name = ""
        last_name = ""
        if full_name:
            parts = full_name.split(" ", 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]
                
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Ensure user has a wallet
        Wallet.objects.get_or_create(user=user)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user
    full_name = f"{user.first_name} {user.last_name}".strip()
    return Response({
        "id": user.id,
        "email": user.email,
        "full_name": full_name or user.username,
        "is_active": user.is_active,
        "is_admin": user.is_staff or user.is_superuser,
    }, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
