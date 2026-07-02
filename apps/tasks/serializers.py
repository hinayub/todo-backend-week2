from datetime import date

from django_rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"

    def validate_date(self, value):
        if value < date.today():
            raise serializers.ValidationError("Date cannot be in the past.")
        return value
