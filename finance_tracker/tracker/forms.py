from django import forms

from .models import Account, Budget, Category, Goal, Transaction


class BaseStyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{classes} form-input".strip()


class AccountForm(BaseStyledForm):
    class Meta:
        model = Account
        fields = ["name", "bank_name", "account_type", "balance", "currency", "is_connected"]


class TransactionForm(BaseStyledForm):
    class Meta:
        model = Transaction
        fields = ["account", "category", "amount", "description", "occurred_at"]
        widgets = {
            "occurred_at": forms.DateInput(attrs={"type": "date"}),
        }


class BudgetForm(BaseStyledForm):
    class Meta:
        model = Budget
        fields = ["name", "amount", "period", "category", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class GoalForm(BaseStyledForm):
    class Meta:
        model = Goal
        fields = ["name", "target_amount", "current_amount", "target_date"]
        widgets = {
            "target_date": forms.DateInput(attrs={"type": "date"}),
        }


class CategoryForm(BaseStyledForm):
    class Meta:
        model = Category
        fields = ["name", "kind"]


class TransactionImportForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.order_by("name"))
    file = forms.FileField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{classes} form-input".strip()
