from django import forms
from django.core.exceptions import ValidationError

from .models import Order, Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'description': forms.Textarea(attrs={'class': 'input', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0.01'}),
            'stock': forms.NumberInput(attrs={'class': 'input', 'min': '0'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 3:
            raise ValidationError('Product name must be at least 3 characters.')
        return name

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise ValidationError('Price must be greater than zero.')
        return price

    def clean_stock(self):
        stock = self.cleaned_data['stock']
        if stock < 0:
            raise ValidationError('Stock cannot be negative.')
        return stock


class OrderForm(forms.ModelForm):
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'input', 'min': '1'}),
    )

    class Meta:
        model = Order
        fields = ['quantity']

    def __init__(self, *args, product=None, **kwargs):
        self.product = product
        super().__init__(*args, **kwargs)

    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if self.product is not None and quantity > self.product.stock:
            raise ValidationError(
                f'Only {self.product.stock} item(s) available in stock.'
            )
        return quantity


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(self.instance.status, self.instance.get_status_display())]
        choices += [
            (value, label)
            for value, label in Order.STATUS_CHOICES
            if self.instance.can_transition_to(value)
        ]
        self.fields['status'].choices = choices

    def clean_status(self):
        new_status = self.cleaned_data['status']
        if new_status != self.instance.status and not self.instance.can_transition_to(new_status):
            raise ValidationError(
                f'An order marked "{self.instance.get_status_display()}" cannot be '
                f'changed to "{dict(Order.STATUS_CHOICES).get(new_status, new_status)}".'
            )
        return new_status
