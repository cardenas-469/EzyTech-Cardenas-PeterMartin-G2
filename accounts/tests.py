from decimal import Decimal
import io
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from products.models import Order, Product

from .models import User


class AccountFeatureTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='StrongPass123!',
            role='admin',
        )
        self.customer = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='StrongPass123!',
            role='customer',
            first_name='Juan',
            last_name='Dela Cruz',
            contact_number='09171234567',
        )
        self.product = Product.objects.create(
            name='Tablet',
            description='A tablet.',
            price=Decimal('500.00'),
            stock=10,
            created_by=self.admin,
        )

    def test_registration_creates_customer_account(self):
        response = self.client.post(
            reverse('register'),
            {
                'first_name': 'Maria',
                'last_name': 'Santos',
                'username': 'mariasantos',
                'email': 'maria@example.com',
                'contact_number': '09170000000',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(username='mariasantos')
        self.assertEqual(user.role, 'customer')
        self.assertContains(response, 'Account created')

    def test_registration_rejects_duplicate_email(self):
        response = self.client.post(
            reverse('register'),
            {
                'first_name': 'Duplicate',
                'last_name': 'Email',
                'username': 'duplicate',
                'email': 'customer@example.com',
                'contact_number': '',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='duplicate').exists())
        self.assertContains(response, 'already exists')

    def test_login_and_role_dashboard_redirect(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'customer', 'password': 'StrongPass123!'},
            follow=True,
        )
        self.assertRedirects(response, reverse('customer_dashboard'))
        self.assertContains(response, 'Customer Dashboard')

    def test_dashboard_redirect_sends_admin_to_admin_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(response, reverse('admin_dashboard'))

    def test_customer_cannot_open_admin_dashboard(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_open_customer_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_profile_requires_login(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_customer_can_update_profile(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('edit_profile'),
            {
                'first_name': 'Juan',
                'last_name': 'Dela Cruz Jr.',
                'email': 'customer@example.com',
                'contact_number': '09998887777',
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('profile'))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.last_name, 'Dela Cruz Jr.')
        self.assertEqual(self.customer.contact_number, '09998887777')
        self.assertContains(response, 'Profile updated successfully')

    def test_customer_dashboard_shows_own_order_stats(self):
        Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=2,
            total_price=Decimal('1000.00'),
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(response.context['order_count'], 1)
        self.assertEqual(response.context['pending_count'], 1)
        self.assertEqual(response.context['total_spent'], Decimal('1000.00'))
        self.assertContains(response, 'Recent orders')

    def test_admin_dashboard_shows_store_stats(self):
        Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=1,
            total_price=Decimal('500.00'),
            status=Order.STATUS_CONFIRMED,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.context['product_count'], 1)
        self.assertEqual(response.context['pending_count'], 0)
        self.assertEqual(response.context['total_sales'], Decimal('500.00'))
        self.assertContains(response, 'Confirmed sales')


class ErrorPageTests(TestCase):
    def test_unknown_url_renders_custom_404(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)

    def test_custom_404_never_shows_a_debug_traceback(self):
        with override_settings(DEBUG=False):
            response = self.client.get('/missing-record/')
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Traceback', status_code=404)
        self.assertNotContains(response, 'DisallowedHost', status_code=404)

    def test_customer_role_violation_renders_custom_403(self):
        customer = User.objects.create_user(
            username='blocked', email='blocked@example.com',
            password='StrongPass123!', role='customer',
        )
        self.client.force_login(customer)
        response = self.client.get(reverse('product_create'))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')
        self.assertContains(response, 'Access denied', status_code=403)

    def test_custom_500_handler_renders_page(self):
        from django.test import RequestFactory

        from config.views import server_error

        response = server_error(RequestFactory().get('/boom/'))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'Something went wrong', status_code=500)


class RegistrationHardeningTests(TestCase):
    def _payload(self, **overrides):
        data = {
            'first_name': 'Maria',
            'last_name': 'Santos',
            'username': 'mariasantos',
            'email': 'maria@example.com',
            'contact_number': '09171234567',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        data.update(overrides)
        return data

    def test_role_cannot_be_injected_through_registration(self):
        response = self.client.post(
            reverse('register'), self._payload(role='admin'), follow=True
        )
        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(username='mariasantos')
        self.assertEqual(user.role, 'customer')

    def test_duplicate_email_is_case_insensitive(self):
        User.objects.create_user(
            username='first', email='maria@example.com',
            password='StrongPass123!', role='customer',
        )
        response = self.client.post(
            reverse('register'), self._payload(email='MARIA@EXAMPLE.COM')
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mariasantos').exists())
        self.assertContains(response, 'already exists')

    def test_invalid_contact_number_is_rejected(self):
        response = self.client.post(
            reverse('register'), self._payload(contact_number='call-me-maybe')
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mariasantos').exists())
        self.assertContains(response, 'valid contact number')


class ProfilePhotoHardeningTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)

        self.customer = User.objects.create_user(
            username='customer', email='customer@example.com',
            password='StrongPass123!', role='customer',
        )
        self.client.force_login(self.customer)

    def _image(self, name='avatar.png', fmt='PNG', content_type='image/png', noise=False):
        buffer = io.BytesIO()
        if noise:
            image = Image.frombytes('RGB', (1000, 1000), os.urandom(3_000_000))
        else:
            image = Image.new('RGB', (32, 32), (30, 90, 160))
        image.save(buffer, format=fmt)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

    def _post(self, photo):
        return self.client.post(
            reverse('edit_profile'),
            {
                'first_name': 'Juan',
                'last_name': 'Dela Cruz',
                'email': 'customer@example.com',
                'contact_number': '09171234567',
                'profile_photo': photo,
            },
        )

    def test_valid_png_photo_is_accepted(self):
        response = self._post(self._image())
        self.assertRedirects(response, reverse('profile'))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.profile_photo.name.endswith('.png'))

    def test_oversized_photo_is_rejected(self):
        response = self._post(self._image(name='large.png', noise=True))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2 MB or smaller')
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.profile_photo)

    def test_unsupported_image_type_is_rejected(self):
        response = self._post(
            self._image(name='avatar.gif', fmt='GIF', content_type='image/gif')
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JPEG, PNG, or WebP')
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.profile_photo)
