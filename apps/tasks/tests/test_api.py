import pytest
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.tasks.models import Task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="hamid", password="Passw0rd!")


@pytest.fixture
def another_user(db):
    return User.objects.create_user(username="ali", password="Passw0rd!")


@pytest.fixture
def future_date():
    # The serializer rejects past dates, so tests always use a future one.
    return timezone.localdate() + timedelta(days=1)


@pytest.fixture
def task(user, future_date):
    return Task.objects.create(
        user=user,
        description="Buy groceries",
        time=time(14, 30),
        date=future_date,
        completed=False,
    )


# ---------------------------------------------------------------------------
# 1. AUTH — happy path: registration issues an access token
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_register_returns_201_and_token(api_client):
    url = reverse("register")
    payload = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "Passw0rd!",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    assert "access" in response.data
    assert response.data["user"]["username"] == "newuser"
    assert User.objects.filter(username="newuser").exists()


# ---------------------------------------------------------------------------
# 2. AUTH — error path: login with a wrong password is rejected
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_login_with_wrong_password_returns_401(api_client, user):
    user.email = "hamid@example.com"
    user.save()

    url = reverse("login")
    payload = {"email": "hamid@example.com", "password": "wrong-password"}
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 401
    assert "access" not in response.data


# ---------------------------------------------------------------------------
# 3. CRUD — create: an authenticated user can create a task
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_authenticated_user_can_create_task(api_client, user, future_date):
    api_client.force_authenticate(user=user)

    url = reverse("task-list-create")
    payload = {
        "description": "Write API tests",
        "time": "09:00:00",
        "date": future_date.isoformat(),
        "completed": False,
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    assert response.data["description"] == "Write API tests"
    # The owner is set from request.user, never from the client payload.
    assert response.data["user"] == user.id
    assert Task.objects.filter(user=user, description="Write API tests").exists()


# ---------------------------------------------------------------------------
# 4. CRUD — read: a user only sees their own tasks in the list
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_list_returns_only_own_tasks(api_client, user, another_user, future_date):
    Task.objects.create(
        user=user, description="Mine", time=time(8, 0), date=future_date
    )
    Task.objects.create(
        user=another_user, description="Theirs", time=time(9, 0), date=future_date
    )

    api_client.force_authenticate(user=user)
    response = api_client.get(reverse("task-list-create"))

    assert response.status_code == 200
    descriptions = [t["description"] for t in response.data]
    assert descriptions == ["Mine"]


# ---------------------------------------------------------------------------
# 5. CRUD — update: the owner can PATCH their own task
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_owner_can_update_task(api_client, user, task):
    api_client.force_authenticate(user=user)

    url = reverse("task-update-delete", args=[task.id])
    response = api_client.patch(url, {"completed": True}, format="json")

    assert response.status_code == 200
    assert response.data["completed"] is True
    task.refresh_from_db()
    assert task.completed is True


# ---------------------------------------------------------------------------
# 6. ERROR — unauthenticated requests to the tasks API are rejected
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_unauthenticated_request_is_rejected(api_client):
    response = api_client.get(reverse("task-list-create"))
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 7. ERROR — a user cannot delete a task owned by someone else
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_user_cannot_delete_another_users_task(
    api_client, user, another_user, future_date
):
    victim_task = Task.objects.create(
        user=another_user,
        description="Not yours",
        time=time(10, 0),
        date=future_date,
    )

    api_client.force_authenticate(user=user)
    url = reverse("task-update-delete", args=[victim_task.id])
    response = api_client.delete(url)

    # IsOwnerOrAdmin denies the object-level check -> 403.
    assert response.status_code == 403
    assert Task.objects.filter(id=victim_task.id).exists()


# ---------------------------------------------------------------------------
# 8. INTEGRATION — full flow starting from authentication:
#    register -> login (real JWT) -> create a task with the Bearer token
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_full_flow_register_login_then_create_task(api_client, future_date):
    # 1. Register a brand-new account. No force_authenticate anywhere in this
    #    test -- every request is authenticated exactly as a real client would.
    register_payload = {
        "username": "integration",
        "email": "integration@example.com",
        "password": "Passw0rd!",
    }
    register_response = api_client.post(
        reverse("register"), register_payload, format="json"
    )
    assert register_response.status_code == 201

    # 2. Log in with the same credentials to obtain a fresh access token,
    #    exercising the real login endpoint rather than reusing register's token.
    login_response = api_client.post(
        reverse("login"),
        {"email": "integration@example.com", "password": "Passw0rd!"},
        format="json",
    )
    assert login_response.status_code == 200
    access_token = login_response.data["access"]
    assert access_token

    # 3. Present the JWT as a Bearer token on the tasks API and create a task.
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    create_response = api_client.post(
        reverse("task-list-create"),
        {
            "description": "End-to-end task",
            "time": "11:15:00",
            "date": future_date.isoformat(),
            "completed": False,
        },
        format="json",
    )
    assert create_response.status_code == 201
    assert create_response.data["description"] == "End-to-end task"

    # 4. The task is persisted and owned by the authenticated user, and it
    #    comes back when that same token lists the tasks.
    created_user = User.objects.get(username="integration")
    assert Task.objects.filter(
        user=created_user, description="End-to-end task"
    ).exists()

    list_response = api_client.get(reverse("task-list-create"))
    assert list_response.status_code == 200
    assert [t["description"] for t in list_response.data] == ["End-to-end task"]
