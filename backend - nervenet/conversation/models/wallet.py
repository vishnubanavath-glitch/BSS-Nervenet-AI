from django.db import models
from django.contrib.auth.models import User

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    total_tokens_used = models.IntegerField(default=0)

    class Meta:
        db_table = "wallets"

    def __str__(self):
        return f"{self.user.username}'s Wallet - ${self.balance}"
