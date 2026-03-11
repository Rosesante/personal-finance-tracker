from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/", views.accounts_page, name="accounts"),
    path("accounts/<int:pk>/delete/", views.account_delete, name="account-delete"),
    path("income/", views.income_page, name="income"),
    path("expenses/", views.expenses_page, name="expenses"),
    path("budgets/", views.budgets_page, name="budgets"),
    path("goals/", views.goals_page, name="goals"),
    path("categories/", views.categories_page, name="categories"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category-edit"),
    path("charts/income-expense/", views.chart_income_expense, name="chart-income-expense"),
    path("charts/spend-trend/", views.chart_spend_trend, name="chart-spend-trend"),
    path("bank/connect/", views.bank_connect, name="bank-connect"),
    path("bank/callback/", views.bank_callback, name="bank-callback"),
    path("bank/sync/", views.bank_sync, name="bank-sync"),
    path("import/", views.import_transactions, name="import-transactions"),
]
