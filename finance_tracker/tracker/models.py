from django.db import models


class Account(models.Model):
    ACCOUNT_TYPES = [
        ("checking", "Checking"),
        ("savings", "Savings"),
        ("credit", "Credit Card"),
        ("cash", "Cash"),
        ("mobile_money", "Mobile Money"),
        ("investment", "Investment"),
    ]

    name = models.CharField(max_length=120)
    bank_name = models.CharField(max_length=120, blank=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default="checking")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="TZS")
    is_connected = models.BooleanField(default=False)
    external_id = models.CharField(max_length=120, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.currency})"


class Category(models.Model):
    KIND_CHOICES = [
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


class Transaction(models.Model):
    KIND_CHOICES = [
        ("income", "Income"),
        ("expense", "Expense"),
        ("transfer", "Transfer"),
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    external_id = models.CharField(max_length=120, blank=True, db_index=True)
    description = models.CharField(max_length=200, blank=True)
    occurred_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.kind}: {self.amount} {self.account.currency}"


class Budget(models.Model):
    PERIOD_CHOICES = [
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
    ]

    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="monthly")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.period})"


class Goal(models.Model):
    name = models.CharField(max_length=120)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class BankConnection(models.Model):
    provider = models.CharField(max_length=60, default="truelayer")
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.provider} connection"
