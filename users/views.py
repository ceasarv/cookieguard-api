from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, LoginSerializer


def get_tokens_for_user(user):
	refresh = RefreshToken.for_user(user)
	return {
		'refresh': str(refresh),
		'access': str(refresh.access_token),
	}


class RegisterView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		serializer = RegisterSerializer(data=request.data)
		if serializer.is_valid():
			user = serializer.save()
			return Response({
				'message': 'User created successfully',
				'user': {
					'id': user.id,
					'email': user.email,
				},
				'tokens': get_tokens_for_user(user)
			}, status=status.HTTP_201_CREATED)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		serializer = LoginSerializer(data=request.data)
		if serializer.is_valid():
			user = serializer.validated_data
			return Response({
				'user': {
					'id': user.id,
					'email': user.email,
				},
				'tokens': get_tokens_for_user(user),
			})
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		user = request.user
		return Response({
			'id': user.id,
			'email': user.email,
		})
