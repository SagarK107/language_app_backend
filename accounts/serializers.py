from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import User


class SignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "id", "username", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_username(self, value):
        if "@" in value:
            raise serializers.ValidationError("Username cannot contain'@'")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A User with that email already exists")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    active_course = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "active_course"]

    def get_active_course(self, user):
        # A user who has not picked a course has no UserActiveCourse row.
        try:
            return user.active_course.course_id
        except ObjectDoesNotExist:
            return None
