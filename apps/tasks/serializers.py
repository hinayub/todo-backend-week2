from datetime import date

from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = ["user", "created_at", "updated_at"]

    def validate_date(self, value):
        if value < date.today():
            raise serializers.ValidationError("Date cannot be in the past.")
        return value
