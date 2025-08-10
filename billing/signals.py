from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import BillingProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_billing_profile(sender, instance, created, **kwargs):
	if created:
		BillingProfile.objects.get_or_create(user=instance)
