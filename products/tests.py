from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User

from .models import Order, Product


class BaseProductTestCase(TestCase):
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
        )
        self.other_customer = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='StrongPass123!',
            role='customer',
        )
        self.product = Product.objects.create(
            name='Laptop Pro',
            description='A powerful laptop.',
            price=Decimal('1500.00'),
            stock=5,
            created_by=self.admin,
        )


class ProductCatalogAccessTests(BaseProductTestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_logged_in_customer_can_view_catalog(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Laptop Pro')
        self.assertContains(response, 'Order now')

    def test_catalog_search_filters_products(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('product_list'), {'q': 'Laptop'})
        self.assertContains(response, 'Laptop Pro')
        response = self.client.get(reverse('product_list'), {'q': 'Phone'})
        self.assertNotContains(response, 'Laptop Pro')


class ProductCrudPermissionTests(BaseProductTestCase):
    def test_customer_cannot_create_product(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('product_create'))
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_update_product(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('product_update', args=[self.product.pk]))
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_delete_product(self):
        self.client.force_login(self.customer)
        response = self.client.post(reverse('product_delete', args=[self.product.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_admin_can_create_product(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('product_create'),
            {
                'name': 'Wireless Mouse',
                'description': 'Ergonomic mouse.',
                'price': '25.50',
                'stock': '10',
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('product_list'))
        product = Product.objects.get(name='Wireless Mouse')
        self.assertEqual(product.created_by, self.admin)
        self.assertContains(response, 'was added successfully')

    def test_admin_can_update_product(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('product_update', args=[self.product.pk]),
            {
                'name': 'Laptop Pro Max',
                'description': 'An even more powerful laptop.',
                'price': '1800.00',
                'stock': '4',
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('product_list'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Laptop Pro Max')
        self.assertEqual(self.product.stock, 4)
        self.assertContains(response, 'was updated successfully')

    def test_admin_can_delete_product_without_orders(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('product_delete', args=[self.product.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse('product_list'))
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertContains(response, 'was deleted')

    def test_product_with_orders_cannot_be_deleted(self):
        Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('product_delete', args=[self.product.pk]),
            follow=True,
        )
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertContains(response, 'cannot be deleted')

    def test_invalid_product_price_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('product_create'),
            {
                'name': 'Broken Product',
                'description': 'Should not be saved.',
                'price': '0.00',
                'stock': '1',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(name='Broken Product').exists())


class CheckoutTests(BaseProductTestCase):
    def test_checkout_requires_login(self):
        response = self.client.get(reverse('order_checkout', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_valid_checkout_creates_order_and_reduces_stock(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_checkout', args=[self.product.pk]),
            {'quantity': '2'},
            follow=True,
        )
        self.assertRedirects(response, reverse('order_history'))
        order = Order.objects.get(user=self.customer)
        self.assertEqual(order.product, self.product)
        self.assertEqual(order.quantity, 2)
        self.assertEqual(order.total_price, Decimal('3000.00'))
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertContains(response, 'placed successfully')

    def test_checkout_rejects_quantity_above_stock(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_checkout', args=[self.product.pk]),
            {'quantity': '6'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertFormError(response.context['form'], 'quantity', 'Only 5 item(s) available in stock.')

    def test_checkout_rejects_zero_quantity(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_checkout', args=[self.product.pk]),
            {'quantity': '0'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertFormError(
            response.context['form'],
            'quantity',
            'Ensure this value is greater than or equal to 1.',
        )


class OrderManagementTests(BaseProductTestCase):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=2,
            total_price=Decimal('3000.00'),
        )
        self.product.stock -= 2
        self.product.save()

    def test_customer_only_sees_own_orders(self):
        Order.objects.create(
            user=self.other_customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_history'))
        self.assertContains(response, f'<td>#{self.order.id}</td>')
        self.assertNotContains(response, self.other_customer.username)

    def test_admin_sees_all_orders(self):
        Order.objects.create(
            user=self.other_customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('order_history'))
        self.assertContains(response, self.customer.username)
        self.assertContains(response, self.other_customer.username)

    def test_customer_can_cancel_own_pending_order(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_cancel', args=[self.order.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse('order_history'))
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CANCELLED)
        self.assertEqual(self.product.stock, 5)
        self.assertContains(response, 'was cancelled')

    def test_customer_cannot_cancel_another_customers_order(self):
        self.client.force_login(self.other_customer)
        response = self.client.post(
            reverse('order_cancel', args=[self.order.pk]),
            follow=True,
        )
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PENDING)
        self.assertEqual(self.product.stock, 3)
        self.assertContains(response, 'only manage your own orders')

    def test_cancelled_order_can_be_deleted_by_customer(self):
        self.order.status = Order.STATUS_CANCELLED
        self.order.save()
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_delete', args=[self.order.pk]),
            follow=True,
        )
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.assertContains(response, 'was deleted')

    def test_pending_order_cannot_be_deleted_by_customer(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_delete', args=[self.order.pk]),
            follow=True,
        )
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())
        self.assertContains(response, 'Only cancelled orders can be deleted')

    def test_admin_can_delete_order_and_stock_is_restored(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('order_delete', args=[self.order.pk]),
            follow=True,
        )
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertContains(response, 'was deleted')

    def test_admin_can_update_order_status(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('order_status_update', args=[self.order.pk]),
            {'status': Order.STATUS_CONFIRMED},
            follow=True,
        )
        self.assertRedirects(response, reverse('order_history'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CONFIRMED)

    def test_admin_cancelling_order_restores_stock(self):
        self.order.status = Order.STATUS_CONFIRMED
        self.order.save()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('order_status_update', args=[self.order.pk]),
            {'status': Order.STATUS_CANCELLED},
            follow=True,
        )
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CANCELLED)
        self.assertEqual(self.product.stock, 5)
        self.assertContains(response, 'status changed')

    def test_invalid_status_transition_is_rejected(self):
        self.order.status = Order.STATUS_COMPLETED
        self.order.save()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('order_status_update', args=[self.order.pk]),
            {'status': Order.STATUS_PENDING},
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_COMPLETED)

    def test_customer_cannot_access_order_status_update(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_status_update', args=[self.order.pk]))
        self.assertEqual(response.status_code, 403)


class OrderDetailAndFilterTests(BaseProductTestCase):
    def setUp(self):
        super().setUp()
        self.pending_order = Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
        )
        self.completed_order = Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=2,
            total_price=self.product.price * 2,
            status=Order.STATUS_COMPLETED,
        )

    def test_owner_can_view_order_detail(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_detail', args=[self.pending_order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Order #{self.pending_order.id}')
        self.assertContains(response, 'Laptop Pro')
        self.assertContains(response, 'Cancel order')

    def test_other_customer_cannot_view_order_detail(self):
        self.client.force_login(self.other_customer)
        response = self.client.get(
            reverse('order_detail', args=[self.pending_order.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse('order_history'))
        self.assertContains(response, 'only view your own orders')

    def test_admin_can_view_any_order_detail(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('order_detail', args=[self.pending_order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.username)
        self.assertContains(response, 'Update status')

    def test_history_can_be_filtered_by_status(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_history'), {'status': Order.STATUS_COMPLETED})
        self.assertContains(response, f'<td>#{self.completed_order.id}</td>')
        self.assertNotContains(response, f'<td>#{self.pending_order.id}</td>')

    def test_history_can_be_searched_by_product(self):
        phone = Product.objects.create(
            name='Nova Phone',
            description='A smartphone.',
            price=Decimal('999.00'),
            stock=3,
            created_by=self.admin,
        )
        phone_order = Order.objects.create(
            user=self.customer,
            product=phone,
            quantity=1,
            total_price=phone.price,
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_history'), {'q': 'Nova Phone'})
        self.assertContains(response, f'<td>#{phone_order.id}</td>')
        self.assertNotContains(response, f'<td>#{self.pending_order.id}</td>')

    def test_admin_can_search_orders_by_customer(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('order_history'), {'q': 'other'})
        self.assertNotContains(response, f'<td>#{self.pending_order.id}</td>')
        response = self.client.get(reverse('order_history'), {'q': 'customer'})
        self.assertContains(response, f'<td>#{self.pending_order.id}</td>')


class SeedProductsCommandTests(BaseProductTestCase):
    def test_seed_products_links_demo_and_ownerless_products_to_admin(self):
        from io import StringIO

        from django.core.management import call_command

        ownerless = Product.objects.create(
            name='Ownerless Item',
            description='Created without an owner.',
            price=Decimal('10.00'),
            stock=1,
        )
        output = StringIO()

        call_command('seed_products', '--admin', self.admin.username, stdout=output)

        self.assertTrue(
            Product.objects.filter(
                name='AeroBook 14 Laptop', created_by=self.admin
            ).exists()
        )
        ownerless.refresh_from_db()
        self.assertEqual(ownerless.created_by, self.admin)
        self.assertIn('ownerless product(s) linked', output.getvalue())

    def test_seed_products_fails_without_an_admin(self):
        from io import StringIO

        from django.core.management import call_command
        from django.core.management.base import CommandError

        User.objects.all().delete()
        with self.assertRaises(CommandError):
            call_command('seed_products', stdout=StringIO())


class AuthenticationAndRoleHardeningTests(BaseProductTestCase):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
        )

    def test_every_core_view_requires_login(self):
        self.client.logout()
        protected_urls = [
            reverse('product_list'),
            reverse('product_create'),
            reverse('product_update', args=[self.product.pk]),
            reverse('product_delete', args=[self.product.pk]),
            reverse('order_checkout', args=[self.product.pk]),
            reverse('order_history'),
            reverse('order_detail', args=[self.order.pk]),
            reverse('order_cancel', args=[self.order.pk]),
            reverse('order_delete', args=[self.order.pk]),
            reverse('order_status_update', args=[self.order.pk]),
        ]
        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302, url)
                self.assertIn(reverse('login'), response.url, url)

    def test_customer_cannot_create_or_delete_products_by_posting(self):
        self.client.force_login(self.customer)
        create_response = self.client.post(
            reverse('product_create'),
            {
                'name': 'Unauthorized Product',
                'description': 'Should never be saved.',
                'price': '10.00',
                'stock': '1',
            },
        )
        delete_response = self.client.post(
            reverse('product_delete', args=[self.product.pk])
        )
        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertFalse(Product.objects.filter(name='Unauthorized Product').exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_customer_cannot_update_order_status(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_status_update', args=[self.order.pk]),
            {'status': Order.STATUS_COMPLETED},
        )
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PENDING)


class CrossUserAccessHardeningTests(BaseProductTestCase):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            user=self.other_customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
            status=Order.STATUS_CANCELLED,
        )

    def test_customer_cannot_delete_another_users_order(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('order_delete', args=[self.order.pk]), follow=True
        )
        self.assertRedirects(response, reverse('order_history'))
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())
        self.assertContains(response, 'only manage your own orders')

    def test_customer_cannot_open_another_users_order_detail(self):
        self.client.force_login(self.customer)
        response = self.client.get(
            reverse('order_detail', args=[self.order.pk]), follow=True
        )
        self.assertRedirects(response, reverse('order_history'))
        self.assertContains(response, 'only view your own orders')

    def test_admin_can_manage_any_customers_order(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.other_customer.username)


class FormValidationHardeningTests(BaseProductTestCase):
    def test_duplicate_product_name_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('product_create'),
            {
                'name': 'Laptop Pro',
                'description': 'A duplicate name.',
                'price': '100.00',
                'stock': '2',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Product.objects.filter(name='Laptop Pro').count(), 1)
        self.assertContains(response, 'already exists')

    def test_invalid_product_update_keeps_original_values(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('product_update', args=[self.product.pk]),
            {
                'name': 'Laptop Pro',
                'description': 'A powerful laptop.',
                'price': '-5.00',
                'stock': '5',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('1500.00'))

    def test_unknown_status_value_is_rejected(self):
        order = Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('order_status_update', args=[order.pk]),
            {'status': 'Hacked'},
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)

    def test_csrf_token_is_required_for_checkout(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.customer)
        response = csrf_client.post(
            reverse('order_checkout', args=[self.product.pk]),
            {'quantity': '1'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)


class UrlAndMethodHardeningTests(BaseProductTestCase):
    def test_unknown_product_id_returns_custom_404(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_checkout', args=[999999]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Page not found', status_code=404)

    def test_unknown_order_id_returns_custom_404(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_detail', args=[999999]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Page not found', status_code=404)

    def test_delete_and_cancel_actions_reject_get_requests(self):
        order = Order.objects.create(
            user=self.customer,
            product=self.product,
            quantity=1,
            total_price=self.product.price,
        )
        self.client.force_login(self.customer)
        cancel_response = self.client.get(reverse('order_cancel', args=[order.pk]))
        delete_response = self.client.get(reverse('order_delete', args=[order.pk]))
        self.assertRedirects(cancel_response, reverse('order_history'))
        self.assertRedirects(delete_response, reverse('order_history'))
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)

    def test_product_delete_get_only_shows_confirmation(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('product_delete', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/product_confirm_delete.html')
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_checkout_cannot_oversell_with_repeated_requests(self):
        self.client.force_login(self.customer)
        first = self.client.post(
            reverse('order_checkout', args=[self.product.pk]), {'quantity': '3'}
        )
        second = self.client.post(
            reverse('order_checkout', args=[self.product.pk]), {'quantity': '3'}
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)
        self.assertContains(second, 'Only 2 item(s) available in stock.')


class DatabaseConstraintTests(BaseProductTestCase):
    def test_duplicate_product_name_is_blocked_by_the_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    name='Laptop Pro',
                    description='Duplicate.',
                    price=Decimal('10.00'),
                    stock=1,
                )

    def test_non_positive_product_price_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    name='Free Item',
                    description='Invalid price.',
                    price=Decimal('0.00'),
                    stock=1,
                )

    def test_negative_stock_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    name='Negative Stock',
                    description='Invalid stock.',
                    price=Decimal('10.00'),
                    stock=-1,
                )

    def test_non_positive_order_quantity_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(
                    user=self.customer,
                    product=self.product,
                    quantity=0,
                    total_price=Decimal('10.00'),
                )

    def test_non_positive_order_total_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(
                    user=self.customer,
                    product=self.product,
                    quantity=1,
                    total_price=Decimal('0.00'),
                )
