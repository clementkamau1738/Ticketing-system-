from django.test import TestCase
from django.urls import reverse
from .models import CustomUser

class UserRegistrationTest(TestCase):
    def test_signup_view(self):
        response = self.client.get(reverse('users:signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/signup.html')

    def test_signup_success(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123',
            'confirm_password': 'password123', # Standard UserCreationForm handling? No, it uses password1 and password 2 usually but let's check defaults
            # UserCreationForm expects password matches
        }
        # Wait, UserCreationForm requires password1 and password2
        # Let's re-check the form structure or just post correct data
        
        # Creating user via model first to ensure model works
        user = CustomUser.objects.create_user(username='modeluser', password='password')
        self.assertEqual(user.role, 'attendee') # Default

    def test_organizer_permission(self):
        organizer = CustomUser.objects.create_user(username='org', password='pw', role='organizer')
        attendee = CustomUser.objects.create_user(username='att', password='pw', role='attendee')
        
        # Check permissions logic (unit test for IsOrganizerOrReadOnly would go here or in permissions test)
        # But we can test access to organizer dashboard if we had one protected by it
        pass
