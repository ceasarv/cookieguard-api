from rest_framework import serializers
from .models import User
from django.contrib.auth import authenticate


class RegisterSerializer(serializers.ModelSerializer):
	password = serializers.CharField(write_only=True, min_length=6)

	class Meta:
		model = User
		fields = ('email', 'password')

	def create(self, validated_data):
		user = User.objects.create_user(
			email=validated_data['email'],
			password=validated_data['password']
		)
		return user


class LoginSerializer(serializers.Serializer):
	email = serializers.EmailField()
	password = serializers.CharField()

	def validate(self, data):
		user = authenticate(**data)
		if user and user.is_active:
			return user
		raise serializers.ValidationError("Invalid credentials")


class UserSerializer(serializers.ModelSerializer):
	created_on = serializers.DateTimeField(source='date_joined', read_only=True)

	class Meta:
		model = User
		fields = ['id', 'email', 'created_on', 'first_name', 'last_name']
