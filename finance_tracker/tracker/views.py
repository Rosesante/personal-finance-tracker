from datetime import date, datetime, timedelta
import secrets
from decimal import Decimal
import csv
import io

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AccountForm, BudgetForm, CategoryForm, GoalForm, TransactionForm, TransactionImportForm
from .models import Account, BankConnection, Budget, Category, Goal, Transaction
from .truelayer import api_get, build_auth_url, exchange_code, refresh_access_token, token_expires_at


def dashboard(request):
    accounts = Account.objects.order_by("name")
    total_balance = sum(account.balance for account in accounts)
    today = timezone.localdate()
    month_start = today.replace(day=1)

    income_total = (
        Transaction.objects.filter(kind="income", occurred_at__gte=month_start, occurred_at__lte=today)
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    expense_total = (
        Transaction.objects.filter(kind="expense", occurred_at__gte=month_start, occurred_at__lte=today)
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    active_budgets_total = (
        Budget.objects.filter(start_date__lte=today, end_date__gte=today)
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    budget_alert = None
    if active_budgets_total and expense_total > active_budgets_total:
        budget_alert = {
            "message": "Spending is above your active budget for this month.",
            "expense_total": expense_total,
            "budget_total": active_budgets_total,
        }

    recent_transactions = (
        Transaction.objects.select_related("account", "category")
        .order_by("-occurred_at", "-id")[:5]
    )

    return render(
        request,
        "tracker/dashboard.html",
        {
            "accounts": accounts,
            "total_balance": total_balance,
            "income_total": income_total,
            "expense_total": expense_total,
            "recent_transactions": recent_transactions,
            "now": today,
            "budget_alert": budget_alert,
        },
    )


def accounts_page(request):
    accounts = Account.objects.order_by("name")
    form = AccountForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        if request.headers.get("HX-Request"):
            return render(
                request,
                "tracker/partials/account_update.html",
                {"accounts": Account.objects.order_by("name"), "form": AccountForm()},
            )
        return redirect("accounts")
    if request.method == "POST" and request.headers.get("HX-Request"):
        return render(
            request,
            "tracker/partials/account_update.html",
            {"accounts": accounts, "form": form},
        )

    return render(request, "tracker/accounts.html", {"accounts": accounts, "form": form})


def account_delete(request, pk: int):
    account = get_object_or_404(Account, pk=pk)
    if request.method == "POST":
        account.delete()
        if request.headers.get("HX-Request"):
            return render(
                request,
                "tracker/partials/account_update.html",
                {"accounts": Account.objects.order_by("name"), "form": AccountForm()},
            )
        return redirect("accounts")
    return redirect("accounts")


def income_page(request):
    return _transaction_page(request, kind="income")


def expenses_page(request):
    return _transaction_page(request, kind="expense")


def _transaction_page(request, kind: str):
    transactions = Transaction.objects.filter(kind=kind).select_related("account", "category").order_by("-occurred_at", "-id")
    categories = Category.objects.filter(kind=kind)
    form = TransactionForm(request.POST or None)
    form.fields["category"].queryset = categories
    form.fields["occurred_at"].initial = timezone.localdate()

    if request.method == "POST" and form.is_valid():
        transaction = form.save(commit=False)
        transaction.kind = kind
        transaction.save()

        account = transaction.account
        if kind == "income":
            account.balance += transaction.amount
        elif kind == "expense":
            account.balance -= transaction.amount
        account.save(update_fields=["balance"])

        if request.headers.get("HX-Request"):
            updated_form = TransactionForm(initial={"occurred_at": timezone.localdate()})
            updated_form.fields["category"].queryset = categories
            return render(
                request,
                "tracker/partials/transaction_update.html",
                {
                    "transactions": Transaction.objects.filter(kind=kind)
                    .select_related("account", "category")
                    .order_by("-occurred_at", "-id"),
                    "form": updated_form,
                    "kind": kind,
                },
            )
        return redirect("income" if kind == "income" else "expenses")
    if request.method == "POST" and request.headers.get("HX-Request"):
        return render(
            request,
            "tracker/partials/transaction_update.html",
            {"transactions": transactions, "form": form, "kind": kind},
        )

    return render(
        request,
        "tracker/transactions.html",
        {
            "transactions": transactions,
            "form": form,
            "kind": kind,
        },
    )


def budgets_page(request):
    budgets = Budget.objects.select_related("category").order_by("-start_date", "-id")
    form = BudgetForm(request.POST or None)
    form.fields["start_date"].initial = timezone.localdate()

    if request.method == "POST" and form.is_valid():
        form.save()
        if request.headers.get("HX-Request"):
            return render(
                request,
                "tracker/partials/budget_update.html",
                {"budgets": Budget.objects.select_related("category").order_by("-start_date", "-id"), "form": BudgetForm()},
            )
        return redirect("budgets")
    if request.method == "POST" and request.headers.get("HX-Request"):
        return render(
            request,
            "tracker/partials/budget_update.html",
            {"budgets": budgets, "form": form},
        )

    return render(request, "tracker/budgets.html", {"budgets": budgets, "form": form})


def goals_page(request):
    goals = Goal.objects.order_by("-created_at")
    form = GoalForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        if request.headers.get("HX-Request"):
            return render(
                request,
                "tracker/partials/goal_update.html",
                {"goals": Goal.objects.order_by("-created_at"), "form": GoalForm()},
            )
        return redirect("goals")
    if request.method == "POST" and request.headers.get("HX-Request"):
        return render(
            request,
            "tracker/partials/goal_update.html",
            {"goals": goals, "form": form},
        )

    return render(request, "tracker/goals.html", {"goals": goals, "form": form})


def import_transactions(request):
    result = None
    error = None
    form = TransactionImportForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        account = form.cleaned_data["account"]
        uploaded = form.cleaned_data["file"]
        try:
            content = uploaded.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            error = "Unsupported file encoding. Please upload a UTF-8 CSV."
        else:
            try:
                reader = csv.DictReader(io.StringIO(content))
            except csv.Error:
                error = "Invalid CSV file."
            else:
                result = _import_csv(reader, account)
                form = TransactionImportForm()

    return render(
        request,
        "tracker/import.html",
        {
            "form": form,
            "result": result,
            "error": error,
        },
    )


def categories_page(request):
    categories = Category.objects.order_by("name")
    form = CategoryForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        if request.headers.get("HX-Request"):
            return render(
                request,
                "tracker/partials/category_update.html",
                {
                    "categories": Category.objects.order_by("name"),
                    "form": CategoryForm(),
                    "form_action": "categories",
                    "submit_label": "Add Category",
                },
            )
        return redirect("categories")
    if request.method == "POST" and request.headers.get("HX-Request"):
        return render(
            request,
            "tracker/partials/category_update.html",
            {
                "categories": categories,
                "form": form,
                "form_action": "categories",
                "submit_label": "Add Category",
            },
        )

    return render(
        request,
        "tracker/categories.html",
        {
            "categories": categories,
            "form": form,
            "form_action": "categories",
            "submit_label": "Add Category",
        },
    )


def category_edit(request, pk: int):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)

    if request.method == "POST" and form.is_valid():
        form.save()
        if request.headers.get("HX-Request"):
            return render(
                request,
                "tracker/partials/category_update.html",
                {
                    "categories": Category.objects.order_by("name"),
                    "form": CategoryForm(),
                    "form_action": "categories",
                    "submit_label": "Add Category",
                },
            )
        return redirect("categories")

    return render(
        request,
        "tracker/partials/category_form_inner.html",
        {
            "form": form,
            "form_action": "category-edit",
            "form_action_id": category.id,
            "submit_label": "Save Category",
        },
    )


def bank_connect(request):
    if not _has_truelayer_config():
        return HttpResponse("Bank sync is not configured for this environment.")

    state = secrets.token_urlsafe(16)
    request.session["truelayer_state"] = state
    return redirect(build_auth_url(state))


def bank_callback(request):
    if not _has_truelayer_config():
        return HttpResponse("Bank sync is not configured for this environment.")

    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code or state != request.session.get("truelayer_state"):
        return HttpResponse("Invalid TrueLayer callback state.")

    token_payload = exchange_code(code)
    connection = _store_connection_tokens(token_payload)
    _sync_truelayer(connection)
    return redirect("accounts")


def bank_sync(request):
    connection = BankConnection.objects.first()
    if not connection or not connection.access_token:
        return HttpResponse("No bank connection found. Connect a bank first.")

    if connection.expires_at and connection.expires_at <= timezone.now():
        if not connection.refresh_token:
            return HttpResponse("Bank session expired. Reconnect your bank.")
        token_payload = refresh_access_token(connection.refresh_token)
        connection = _store_connection_tokens(token_payload, connection)

    _sync_truelayer(connection)
    return redirect("accounts")


def chart_income_expense(request):
    labels, income_series, expense_series = _chart_series(6)
    return JsonResponse(
        {
            "labels": labels,
            "income": income_series,
            "expenses": expense_series,
        }
    )


def chart_spend_trend(request):
    labels, _, expense_series = _chart_series(6)
    return JsonResponse(
        {
            "labels": labels,
            "expenses": expense_series,
        }
    )


def _chart_series(month_count: int):
    months = _month_range(month_count)
    start = months[0]

    raw = (
        Transaction.objects.filter(occurred_at__gte=start)
        .annotate(month=TruncMonth("occurred_at"))
        .values("month", "kind")
        .annotate(total=Sum("amount"))
    )
    totals = {(row["month"], row["kind"]): row["total"] for row in raw}

    labels = [month.strftime("%b %Y") for month in months]
    income_series = [float(totals.get((month, "income"), 0) or 0) for month in months]
    expense_series = [float(totals.get((month, "expense"), 0) or 0) for month in months]
    return labels, income_series, expense_series


def _month_range(month_count: int):
    today = timezone.localdate()
    start_month = _add_months(today.replace(day=1), -(month_count - 1))
    return [_add_months(start_month, offset) for offset in range(month_count)]


def _add_months(value: date, offset: int):
    year = value.year + (value.month - 1 + offset) // 12
    month = (value.month - 1 + offset) % 12 + 1
    return date(year, month, 1)


def _has_truelayer_config() -> bool:
    from django.conf import settings

    return bool(settings.TRUELAYER_CLIENT_ID and settings.TRUELAYER_CLIENT_SECRET)


def _store_connection_tokens(payload: dict, connection: BankConnection | None = None) -> BankConnection:
    if connection is None:
        connection = BankConnection.objects.first() or BankConnection()
    connection.access_token = payload.get("access_token", connection.access_token)
    connection.refresh_token = payload.get("refresh_token", connection.refresh_token)
    expires_in = payload.get("expires_in")
    if expires_in:
        connection.expires_at = token_expires_at(int(expires_in))
    connection.save()
    return connection


def _sync_truelayer(connection: BankConnection):
    accounts_payload = api_get("/data/v1/accounts", connection.access_token)
    accounts = accounts_payload.get("results") or accounts_payload.get("accounts") or []

    for remote in accounts:
        external_id = remote.get("account_id") or remote.get("id") or ""
        name = remote.get("display_name") or remote.get("name") or "Bank Account"
        currency = remote.get("currency") or "USD"
        account_type_raw = (remote.get("account_type") or "").lower()
        account_type = _map_account_type(account_type_raw)

        account, _created = Account.objects.get_or_create(external_id=external_id, defaults={
            "name": name,
            "bank_name": "TrueLayer",
            "account_type": account_type,
            "currency": currency,
            "is_connected": True,
        })
        account.name = name
        account.bank_name = "TrueLayer"
        account.account_type = account_type
        account.currency = currency
        account.is_connected = True
        account.last_synced_at = timezone.now()

        balance_payload = api_get(f"/data/v1/accounts/{external_id}/balance", connection.access_token)
        balances = balance_payload.get("results") or []
        if balances:
            balance_entry = balances[0]
            raw_balance = (
                balance_entry.get("current")
                or balance_entry.get("available")
                or balance_entry.get("amount")
                or 0
            )
            account.balance = Decimal(str(raw_balance))
        account.save()

        _sync_transactions(connection, account, external_id)


def _sync_transactions(connection: BankConnection, account: Account, external_id: str):
    today = timezone.localdate()
    start = today - timedelta(days=30)
    transactions_payload = api_get(
        f"/data/v1/accounts/{external_id}/transactions?from={start}&to={today}",
        connection.access_token,
    )
    transactions = transactions_payload.get("results") or []

    for entry in transactions:
        tx_id = entry.get("transaction_id") or entry.get("id") or ""
        if tx_id and Transaction.objects.filter(external_id=tx_id).exists():
            continue

        raw_amount = Decimal(str(entry.get("amount", 0)))
        kind = "income" if raw_amount > 0 else "expense"
        amount = raw_amount if raw_amount > 0 else abs(raw_amount)
        description = entry.get("description") or entry.get("merchant_name") or "Bank transaction"
        occurred_at = _parse_date(entry.get("timestamp") or entry.get("transaction_timestamp") or entry.get("date"))

        Transaction.objects.create(
            account=account,
            category=None,
            kind=kind,
            amount=amount,
            external_id=tx_id,
            description=description,
            occurred_at=occurred_at,
        )


def _parse_date(value: str | None):
    if not value:
        return timezone.localdate()
    if "T" in value:
        value = value.split("T")[0]
    return date.fromisoformat(value)


def _map_account_type(raw: str) -> str:
    if "savings" in raw:
        return "savings"
    if "credit" in raw:
        return "credit"
    if "cash" in raw:
        return "cash"
    if "investment" in raw:
        return "investment"
    return "checking"


def _import_csv(reader: csv.DictReader, account: Account):
    required = {"date", "description", "amount"}
    headers = {name.strip().lower() for name in (reader.fieldnames or [])}
    if not required.issubset(headers):
        missing = ", ".join(sorted(required - headers))
        return {"error": f"Missing required columns: {missing}. Use Date, Description, Amount headers."}

    imported = 0
    skipped = 0
    balance_delta = Decimal("0")

    for row in reader:
        try:
            raw_date = row.get("Date") or row.get("date") or ""
            raw_desc = row.get("Description") or row.get("description") or ""
            raw_amount = row.get("Amount") or row.get("amount") or ""
            if not raw_amount.strip():
                skipped += 1
                continue
            amount_value = _parse_amount(raw_amount)
            occurred_at = _parse_date_flexible(raw_date)
        except Exception:
            skipped += 1
            continue

        kind = "income" if amount_value > 0 else "expense"
        amount = amount_value if amount_value > 0 else abs(amount_value)

        Transaction.objects.create(
            account=account,
            category=None,
            kind=kind,
            amount=amount,
            external_id="",
            description=raw_desc.strip(),
            occurred_at=occurred_at,
        )
        balance_delta += amount_value
        imported += 1

    account.balance += balance_delta
    account.save(update_fields=["balance"])

    return {
        "imported": imported,
        "skipped": skipped,
    }


def _parse_amount(value: str) -> Decimal:
    cleaned = value.replace(",", "").replace("TSh", "").replace("TZS", "").strip()
    return Decimal(cleaned)


def _parse_date_flexible(value: str):
    value = (value or "").strip()
    if not value:
        return timezone.localdate()
    if "T" in value:
        value = value.split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return date.fromisoformat(value) if fmt == "%Y-%m-%d" else datetime.strptime(value, fmt).date()
        except Exception:
            continue
    try:
        return date.fromisoformat(value)
    except Exception:
        return timezone.localdate()
