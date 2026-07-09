import pytest
from datetime import date, time
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.tasks.models import Task

@pytest.fixture
def user():
    return User.objects.create_user(
        username="hina",
        password="12345678"
    )

@pytest.fixture
def another_user():
    return User.objects.create_user(
        username="ali",
        password="12345678"
    )

@pytest.fixture
def admin_user():
    admin = User.objects.create_user(
        username="admin",
        password="12345678"
    )
    admin.profile.role = "admin"
    admin.profile.save()
    return admin

@pytest.fixture
def task(user):
    return Task.objects.create(
        user=user,
        description="Buy groceries",
        time=time(14, 30),
        date=date(2026, 7, 10),
        completed=False
    )

@pytest.fixture
def api_client():
    return APIClient()


# Task Model Tests
@pytest.mark.django_db
class TestTaskModel:
    def test_task_creation(self, task, user):
        assert task.user == user
        assert task.description == "Buy groceries"
        assert task.time == time(14, 30)
        assert task.date == date(2026, 7, 10)
        assert task.completed is False
        assert task.created_at is not None
        assert task.updated_at is not None

    def test_task_str_representation(self, task):
        assert str(task) == "Buy groceries"

    def test_task_completed_default_false(self, user):
        task = Task.objects.create(
            user=user,
            description="Test task",
            time=time(10, 0),
            date=date(2026, 7, 5)
        )
        assert task.completed is False

    def test_task_timestamps(self, task):
        assert task.created_at.date() == date.today()
        assert task.updated_at.date() == date.today()

    def test_task_update_updates_timestamp(self, task):
        original_updated_at = task.updated_at
        task.description = "Updated description"
        task.save()
        assert task.updated_at >= original_updated_at

    def test_task_deletion_cascade(self, user):
        task = Task.objects.create(
            user=user,
            description="Task to delete",
            time=time(12, 0),
            date=date(2026, 7, 5)
        )
        task_id = task.id
        user.delete()
        assert not Task.objects.filter(id=task_id).exists()


# Task Views Tests
@pytest.mark.django_db
class TestTaskListCreateView:
    def test_list_tasks_authenticated(self, api_client, user, task):
        api_client.force_authenticate(user=user)
        response = api_client.get('/api/tasks/')
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['id'] == task.id
        assert response.data[0]['description'] == "Buy groceries"

    def test_list_tasks_unauthenticated(self, api_client):
        response = api_client.get('/api/tasks/')
        assert response.status_code == 403

    def test_list_tasks_filters_by_user(self, api_client, user, another_user):
        task1 = Task.objects.create(
            user=user,
            description="User 1 task",
            time=time(10, 0),
            date=date(2026, 7, 5)
        )
        Task.objects.create(
            user=another_user,
            description="User 2 task",
            time=time(11, 0),
            date=date(2026, 7, 5)
        )

        api_client.force_authenticate(user=user)
        response = api_client.get('/api/tasks/')
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['id'] == task1.id
        assert response.data[0]['description'] == "User 1 task"

    def test_create_task_authenticated(self, api_client, user):
        api_client.force_authenticate(user=user)
        payload = {
            'description': 'New task',
            'time': '15:30',
            'date': '2026-07-15',
            'completed': False
        }
        response = api_client.post('/api/tasks/', payload)
        assert response.status_code == 201
        assert response.data['description'] == 'New task'
        assert response.data['user'] == user.id
        assert Task.objects.filter(user=user, description='New task').exists()

    def test_create_task_unauthenticated(self, api_client):
        payload = {
            'description': 'New task',
            'time': '15:30',
            'date': '2026-07-15'
        }
        response = api_client.post('/api/tasks/', payload)
        assert response.status_code == 403

    def test_create_task_assigns_current_user(self, api_client, user):
        api_client.force_authenticate(user=user)
        payload = {
            'description': 'Task for current user',
            'time': '16:00',
            'date': '2026-07-16'
        }
        response = api_client.post('/api/tasks/', payload)
        assert response.status_code == 201
        task = Task.objects.get(description='Task for current user')
        assert task.user == user


@pytest.mark.django_db
class TestTaskUpdateView:
    def test_update_task_authenticated(self, api_client, user, task):
        api_client.force_authenticate(user=user)
        payload = {
            'description': 'Updated description',
            'time': '18:00',
            'date': '2026-07-20',
            'completed': True
        }
        response = api_client.put(f'/api/tasks/{task.id}/', payload)
        assert response.status_code == 200
        task.refresh_from_db()
        assert task.description == 'Updated description'
        assert task.completed is True

    def test_update_task_unauthenticated(self, api_client, task):
        payload = {'description': 'Updated'}
        response = api_client.put(f'/api/tasks/{task.id}/', payload)
        assert response.status_code == 403

    def test_update_task_forbidden_different_user(self, api_client, another_user, task):
        api_client.force_authenticate(user=another_user)
        payload = {'description': 'Hacked!'}
        response = api_client.put(f'/api/tasks/{task.id}/', payload)
        assert response.status_code == 403

    def test_partial_update_task(self, api_client, user, task):
        api_client.force_authenticate(user=user)
        payload = {'completed': True}
        response = api_client.patch(f'/api/tasks/{task.id}/', payload)
        assert response.status_code == 200
        task.refresh_from_db()
        assert task.completed is True
        assert task.description == 'Buy groceries'


@pytest.mark.django_db
class TestTaskDeleteView:
    def test_delete_task_authenticated(self, api_client, user, task):
        task_id = task.id
        api_client.force_authenticate(user=user)
        response = api_client.delete(f'/api/tasks/{task_id}/')
        assert response.status_code == 204
        assert not Task.objects.filter(id=task_id).exists()

    def test_delete_task_unauthenticated(self, api_client, task):
        response = api_client.delete(f'/api/tasks/{task.id}/')
        assert response.status_code == 403

    def test_delete_task_forbidden_different_user(self, api_client, another_user, task):
        api_client.force_authenticate(user=another_user)
        response = api_client.delete(f'/api/tasks/{task.id}/')
        assert response.status_code == 403
        assert Task.objects.filter(id=task.id).exists()


@pytest.mark.django_db
class TestTaskRoleBasedAccess:
    def test_admin_can_list_other_users_tasks(self, api_client, admin_user, task):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get('/api/tasks/')
        assert response.status_code == 200
        assert any(t['id'] == task.id for t in response.data)

    def test_regular_user_cannot_see_other_users_tasks(self, api_client, another_user, task):
        api_client.force_authenticate(user=another_user)
        response = api_client.get('/api/tasks/')
        assert response.status_code == 200
        assert all(t['id'] != task.id for t in response.data)

    def test_admin_can_update_other_users_task(self, api_client, admin_user, task):
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(f'/api/tasks/{task.id}/', {'description': 'Updated by admin'})
        assert response.status_code == 200
        task.refresh_from_db()
        assert task.description == 'Updated by admin'

    def test_admin_can_delete_other_users_task(self, api_client, admin_user, task):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f'/api/tasks/{task.id}/')
        assert response.status_code == 204
        assert not Task.objects.filter(id=task.id).exists()
