"""Seed demo products and make sure every product has an owner.

PD2 ISS-02 reported that the old ``sample_products`` fixture created products
with ``created_by = NULL``. This command replaces that fixture: it links the
demo products (and any ownerless product already in the database) to a real
administrator account.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from products.models import Product

SAMPLE_PRODUCTS = [
    {
        'name': 'AeroBook 14 Laptop',
        'description': '14-inch productivity laptop with 16GB RAM and 512GB SSD.',
        'price': Decimal('54999.00'),
        'stock': 8,
    },
    {
        'name': 'Nova Wireless Mouse',
        'description': 'Ergonomic wireless mouse with silent clicks and USB-C charging.',
        'price': Decimal('1299.00'),
        'stock': 25,
    },
    {
        'name': 'Pulse Mechanical Keyboard',
        'description': 'Hot-swappable mechanical keyboard with RGB backlighting.',
        'price': Decimal('3499.00'),
        'stock': 15,
    },
]


class Command(BaseCommand):
    help = 'Create sample products owned by an admin and fix products with no owner.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin',
            dest='admin_username',
            help='Username of the admin who should own the demo products.',
        )

    def handle(self, *args, **options):
        username = options.get('admin_username')
        if username:
            admin = User.objects.filter(username=username, role='admin').first()
            if admin is None:
                raise CommandError(
                    f'No admin account found with username "{username}".'
                )
        else:
            admin = User.objects.filter(role='admin').order_by('id').first()
            if admin is None:
                raise CommandError(
                    'No admin account exists. Create one with '
                    '"python manage.py createsuperuser" first, or pass --admin USERNAME.'
                )

        created = 0
        updated = 0
        for data in SAMPLE_PRODUCTS:
            product, was_created = Product.objects.update_or_create(
                name=data['name'],
                defaults={
                    'description': data['description'],
                    'price': data['price'],
                    'stock': data['stock'],
                    'created_by': admin,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        # Repair rows left ownerless by the old fixture.
        repaired = Product.objects.filter(created_by__isnull=True).update(created_by=admin)

        self.stdout.write(
            self.style.SUCCESS(
                f'Sample data ready: {created} created, {updated} updated, '
                f'{repaired} ownerless product(s) linked to "{admin.username}".'
            )
        )
