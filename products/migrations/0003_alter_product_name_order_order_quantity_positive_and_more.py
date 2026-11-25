from decimal import Decimal

from django.db import migrations, models


def clean_existing_rows(apps, schema_editor):
    """Make legacy rows valid before unique/check constraints are applied."""
    Product = apps.get_model('products', 'Product')
    Order = apps.get_model('products', 'Order')

    used_names = set()
    for product in Product.objects.order_by('pk'):
        base = (product.name or '').strip() or 'Product'
        name = base
        counter = 2
        while name in used_names:
            suffix = f' ({counter})'
            name = f'{base[:150 - len(suffix)]}{suffix}'
            counter += 1
        used_names.add(name)

        changed = []
        if product.name != name:
            product.name = name
            changed.append('name')
        if product.price is None or product.price <= 0:
            product.price = Decimal('0.01')
            changed.append('price')
        if product.stock is None or product.stock < 0:
            product.stock = 0
            changed.append('stock')
        if changed:
            product.save(update_fields=changed)

    for order in Order.objects.select_related('product').order_by('pk'):
        changed = []
        if order.quantity is None or order.quantity < 1:
            order.quantity = 1
            changed.append('quantity')
        if order.total_price is None or order.total_price <= 0:
            unit_price = order.product.price if order.product else Decimal('0.01')
            order.total_price = (unit_price or Decimal('0.01')) * (order.quantity or 1)
            changed.append('total_price')
        if changed:
            order.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_alter_order_options_alter_product_options_and_more'),
    ]

    operations = [
        migrations.RunPython(clean_existing_rows, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='product',
            name='name',
            field=models.CharField(max_length=150, unique=True),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(check=models.Q(('quantity__gte', 1)), name='order_quantity_positive'),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(check=models.Q(('total_price__gt', 0)), name='order_total_price_positive'),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.CheckConstraint(check=models.Q(('price__gt', 0)), name='product_price_positive'),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.CheckConstraint(check=models.Q(('stock__gte', 0)), name='product_stock_non_negative'),
        ),
    ]
