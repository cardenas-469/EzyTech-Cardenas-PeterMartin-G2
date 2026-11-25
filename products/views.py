from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required

from .forms import OrderForm, OrderStatusForm, ProductForm
from .models import Order, Product


@login_required
def product_list(request):
    products = Product.objects.all()
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(name__icontains=query) | products.filter(
            description__icontains=query
        )
    products = products.distinct()
    return render(
        request,
        'products/product_list.html',
        {'products': products, 'query': query},
    )


@role_required('admin')
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            messages.success(request, f'Product "{product.name}" was added successfully.')
            return redirect('product_list')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProductForm()
    return render(request, 'products/product_form.html', {'form': form, 'is_edit': False})


@role_required('admin')
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" was updated successfully.')
            return redirect('product_list')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProductForm(instance=product)
    return render(
        request,
        'products/product_form.html',
        {'form': form, 'product': product, 'is_edit': True},
    )


@role_required('admin')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        try:
            name = product.name
            product.delete()
            messages.success(request, f'Product "{name}" was deleted.')
        except ProtectedError:
            messages.error(
                request,
                'This product cannot be deleted because it has existing orders. '
                'Products with order history must be kept for record keeping.',
            )
        return redirect('product_list')
    return render(request, 'products/product_confirm_delete.html', {'product': product})


@login_required
def order_checkout(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.method == 'POST':
        form = OrderForm(request.POST, product=product)
        if form.is_valid():
            requested_quantity = form.cleaned_data['quantity']
            with transaction.atomic():
                locked_product = Product.objects.select_for_update().get(pk=product.pk)
                if requested_quantity > locked_product.stock:
                    form.add_error(
                        'quantity',
                        f'Only {locked_product.stock} item(s) available in stock.',
                    )
                else:
                    order = Order.objects.create(
                        user=request.user,
                        product=locked_product,
                        quantity=requested_quantity,
                        total_price=locked_product.price * requested_quantity,
                    )
                    locked_product.stock -= requested_quantity
                    locked_product.save(update_fields=['stock'])
                    messages.success(
                        request,
                        f'Order #{order.id} placed successfully. '
                        f'Total: ${order.total_price}.',
                    )
                    return redirect('order_history')
            messages.error(request, 'Your order could not be placed. Please check the form.')
        else:
            messages.error(request, 'Your order could not be placed. Please check the form.')
    else:
        form = OrderForm(product=product)

    return render(
        request,
        'products/checkout.html',
        {'product': product, 'form': form},
    )


@login_required
def order_history(request):
    is_admin = request.user.role == 'admin'
    orders = Order.objects.select_related('product', 'user')
    if not is_admin:
        orders = orders.filter(user=request.user)

    status_filter = request.GET.get('status', '').strip()
    valid_statuses = {value for value, _ in Order.STATUS_CHOICES}
    if status_filter in valid_statuses:
        orders = orders.filter(status=status_filter)
    else:
        status_filter = ''

    query = request.GET.get('q', '').strip()
    if query:
        matching = orders.filter(product__name__icontains=query)
        if is_admin:
            matching = matching | orders.filter(user__username__icontains=query)
        orders = matching.distinct()

    return render(
        request,
        'products/order_history.html',
        {
            'orders': orders,
            'is_admin': is_admin,
            'status_filter': status_filter,
            'status_choices': Order.STATUS_CHOICES,
            'query': query,
        },
    )


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('product', 'user'),
        pk=pk,
    )
    is_admin = request.user.role == 'admin'
    if order.user_id != request.user.id and not is_admin:
        messages.error(request, 'You can only view your own orders.')
        return redirect('order_history')

    return render(
        request,
        'products/order_detail.html',
        {'order': order, 'is_admin': is_admin},
    )


@login_required
def order_cancel(request, pk):
    if request.method != 'POST':
        return redirect('order_history')

    with transaction.atomic():
        # Lock the order row so two concurrent requests cannot restore stock twice.
        order = get_object_or_404(
            Order.objects.select_for_update().select_related('product'), pk=pk
        )
        if order.user_id != request.user.id and request.user.role != 'admin':
            messages.error(request, 'You can only manage your own orders.')
            return redirect('order_history')

        if not order.can_be_cancelled:
            messages.error(
                request,
                f'Order #{order.id} cannot be cancelled because it is already '
                f'{order.get_status_display()}.',
            )
            return redirect('order_history')

        product = Product.objects.select_for_update().get(pk=order.product_id)
        product.stock += order.quantity
        product.save(update_fields=['stock'])
        order.status = Order.STATUS_CANCELLED
        order.save(update_fields=['status'])

    messages.success(request, f'Order #{order.id} was cancelled and the stock was restored.')
    return redirect('order_history')


@login_required
def order_delete(request, pk):
    if request.method != 'POST':
        return redirect('order_history')

    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=pk)
        is_admin = request.user.role == 'admin'

        if order.user_id != request.user.id and not is_admin:
            messages.error(request, 'You can only manage your own orders.')
            return redirect('order_history')

        if not is_admin and order.status != Order.STATUS_CANCELLED:
            messages.error(request, 'Only cancelled orders can be deleted.')
            return redirect('order_history')

        order_id = order.id
        # Cancelled orders already returned their stock, and completed sales
        # are final. Any other status still holds reserved stock.
        if order.status not in (Order.STATUS_CANCELLED, Order.STATUS_COMPLETED):
            product = Product.objects.select_for_update().get(pk=order.product_id)
            product.stock += order.quantity
            product.save(update_fields=['stock'])
        order.delete()

    messages.success(request, f'Order #{order_id} was deleted.')
    return redirect('order_history')


@role_required('admin')
def order_status_update(request, pk):
    order = get_object_or_404(Order.objects.select_related('product', 'user'), pk=pk)

    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            with transaction.atomic():
                # Re-read and lock the order so parallel updates cannot both
                # apply a status change or restore stock twice.
                locked_order = (
                    Order.objects.select_for_update()
                    .select_related('product')
                    .get(pk=pk)
                )
                previous_status = locked_order.status
                if (
                    new_status != previous_status
                    and not locked_order.can_transition_to(new_status)
                ):
                    messages.error(
                        request,
                        'This order changed while you were updating it. '
                        'Please review the current status and try again.',
                    )
                    return redirect('order_history')

                if (
                    new_status == Order.STATUS_CANCELLED
                    and previous_status != Order.STATUS_CANCELLED
                ):
                    product = Product.objects.select_for_update().get(
                        pk=locked_order.product_id
                    )
                    product.stock += locked_order.quantity
                    product.save(update_fields=['stock'])

                locked_order.status = new_status
                locked_order.save(update_fields=['status'])

            messages.success(
                request,
                f'Order #{locked_order.id} status changed from '
                f'{previous_status} to {new_status}.',
            )
            return redirect('order_history')
        messages.error(request, 'Please choose a valid status.')
    else:
        form = OrderStatusForm(instance=order)

    return render(request, 'products/order_status_form.html', {'form': form, 'order': order})
