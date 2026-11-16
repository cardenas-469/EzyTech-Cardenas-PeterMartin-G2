from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

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
