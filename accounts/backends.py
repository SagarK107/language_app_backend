from django.contrib.auth.backends import ModelBackend

from .models import User


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):

        if username and "@" in username:
            try:
                user = User.objects.get(email=username.lower())
                username = user.username
            except User.DoesNotExist:
                pass

        return super().authenticate(
            request, username=username, password=password, **kwargs
        )
