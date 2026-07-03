from django.urls import path

from .views import (
    TaskListCreateView,
    TaskUpdateDeleteView,
)

urlpatterns = [
    path("", TaskListCreateView.as_view(), name="task-list-create"),
    path("<int:pk>/", TaskUpdateDeleteView.as_view(), name="task-update-delete"),
]
