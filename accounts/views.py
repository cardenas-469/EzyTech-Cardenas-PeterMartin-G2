from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect

from .decorators import role_required
from .forms import RegisterForm, ProfileForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created! You can now log in.')
            return redirect('login')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard_redirect(request):
    if request.user.role == 'admin':
        return redirect('admin_dashboard')
    return redirect('customer_dashboard')


@role_required('admin')
def admin_dashboard(request):
    from products.models import Order, Product

    active_orders = Order.objects.filter(
        status__in=[Order.STATUS_PENDING, Order.STATUS_CONFIRMED, Order.STATUS_SHIPPED]
    )
    sales = Order.objects.filter(
        status__in=[Order.STATUS_CONFIRMED, Order.STATUS_SHIPPED, Order.STATUS_COMPLETED]
    ).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')

    context = {
        'product_count': Product.objects.count(),
        'low_stock_count': Product.objects.filter(stock__lte=5).count(),
        'pending_count': Order.objects.filter(status=Order.STATUS_PENDING).count(),
        'active_order_count': active_orders.count(),
        'total_sales': sales,
        'recent_orders': Order.objects.select_related('user', 'product')[:5],
    }
    return render(request, 'accounts/admin_dashboard.html', context)


@role_required('customer')
def customer_dashboard(request):
    from products.models import Order

    my_orders = Order.objects.filter(user=request.user).select_related('product')
    context = {
        'order_count': my_orders.count(),
        'pending_count': my_orders.filter(status=Order.STATUS_PENDING).count(),
        'completed_count': my_orders.filter(status=Order.STATUS_COMPLETED).count(),
        'total_spent': my_orders.exclude(status=Order.STATUS_CANCELLED).aggregate(
            total=Sum('total_price')
        )['total'] or Decimal('0.00'),
        'recent_orders': my_orders[:3],
    }
    return render(request, 'accounts/customer_dashboard.html', context)


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'profile_user': request.user})


@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/edit_profile.html', {'form': form})
