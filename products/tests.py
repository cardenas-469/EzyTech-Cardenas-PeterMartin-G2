from decimal import Decimal

from django.test import TestCase
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
