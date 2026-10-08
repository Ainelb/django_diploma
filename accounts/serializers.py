from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile


class RegisterSerializer(serializers.ModelSerializer):
    """При регистрации новый пользователь получает роль «Менеджер», повысить роль может только администратор."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label='Повтор пароля')

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password', 'password2')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password2': 'Пароли не совпадают.'})
        return attrs

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Пользователь с таким email уже существует.')
        return value

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()  # профиль с ролью «Менеджер» создаётся сигналом
        return user


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(source='profile.role', choices=Profile.Role.choices, required=False)
    role_display = serializers.CharField(source='profile.get_role_display', read_only=True)
    phone = serializers.CharField(source='profile.phone', required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'is_active', 'role', 'role_display', 'phone')
        read_only_fields = ('id', 'username')

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        for attr, value in profile_data.items():
            setattr(instance.profile, attr, value)
        instance.profile.save()
        return instance


class MeSerializer(UserSerializer):
    """Свой профиль: роль и активность менять нельзя."""

    class Meta(UserSerializer.Meta):
        read_only_fields = ('id', 'username', 'role', 'is_active')