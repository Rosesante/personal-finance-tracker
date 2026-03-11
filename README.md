# Personal Finance Tracker

A Django-based personal finance tracker with a modern UI, instant updates (HTMX), dashboards, budgets, goals, categories, and CSV import.

## Features
- Dashboard with charts (income vs expenses, spend trend)
- Accounts, income, expenses, budgets, goals, categories
- Instant UI updates with HTMX
- CSV import for transactions
- TZS currency formatting

## Prerequisites
- Python 3.11+ (or compatible with your Django version)
- Windows PowerShell (commands below)

## Setup
```powershell
# Create and activate virtualenv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install django

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Start the server
python manage.py runserver
```

Open `http://localhost:8000/`.

## CSV Import Format
The importer expects a CSV file with headers:

```
Date,Description,Amount
2026-03-01,Salary,2500000
2026-03-02,Groceries,-45000
```

## Notes
- Bank sync for Tanzanian banks isn?t available via TrueLayer; use CSV import instead.

## License
Private
