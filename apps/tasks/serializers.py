from rest_framework import serializers
from .models import Task
from django.utils import timezone

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'
        # The view sets the owner via serializer.save(user=request.user),
        # so the client must not (and cannot) supply it.
        read_only_fields = ['user']

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError(
                "Date cannot be in the past."
            )
        return value