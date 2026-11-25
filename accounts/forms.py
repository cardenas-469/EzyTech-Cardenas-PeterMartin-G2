import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import User

CONTACT_NUMBER_RE = re.compile(r'^[0-9+()\-\s]{7,20}$')
ALLOWED_PHOTO_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


class ContactNumberMixin:
    """Shared server-side validation for the optional contact number field."""

    def clean_contact_number(self):
        value = (self.cleaned_data.get('contact_number') or '').strip()
        if value and not CONTACT_NUMBER_RE.fullmatch(value):
            raise ValidationError(
                'Enter a valid contact number (7–20 characters using digits, '
                'spaces, +, -, or parentheses).'
            )
        return value


class UniqueEmailMixin:
    """Reject e-mail addresses that differ only by letter case."""

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise ValidationError('This field is required.')
        matches = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise ValidationError('An account with this email already exists.')
        return email


class RegisterForm(ContactNumberMixin, UniqueEmailMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'contact_number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ('first_name', 'last_name', 'email'):
            self.fields[field].required = True


class ProfileForm(ContactNumberMixin, UniqueEmailMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'contact_number', 'profile_photo')

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        # An existing saved file has no content_type; only new uploads are checked.
        if not photo or not hasattr(photo, 'content_type'):
            return photo
        if photo.size > settings.MAX_PROFILE_PHOTO_SIZE:
            raise ValidationError('Profile photo must be 2 MB or smaller.')
        if photo.content_type not in ALLOWED_PHOTO_TYPES:
            raise ValidationError('Upload a JPEG, PNG, or WebP image.')
        return photo
