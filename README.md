# EzyTech – Project Development 2 (PD2)

EzyTech is a Django + PostgreSQL e-commerce platform for technology products. This repository contains the Account feature from Project Development 1 plus the PD2 core feature: **Product Catalog & Order Management**, implemented as a full vertical slice (database → backend → templates).

## Core Feature (Vertical Slice)

Customers can browse the product catalog, view live stock, place an order through a checkout form, and track or cancel their orders. Administrators manage the catalog and process customer orders.

**Database**
- `Product`: name, description, price, stock, `created_by` (FK → `User`), created date.
- `Order`: `user` (FK → `User`), `product` (FK → `Product`, protected), quantity, total price, status, created date.
- Status flow: `Pending → Confirmed → Shipped → Completed`; `Pending`/`Confirmed` can be cancelled.
- Migrations: `products/migrations/0001_initial.py`, `0002_...py`.

**Backend**
- Views/forms/URLs for product list, search, create, update, delete, checkout, order history, cancel, delete, and admin status updates.
- Checkout uses `transaction.atomic()` + `select_for_update()` so stock cannot be oversold by concurrent requests.
- Quantity must be between 1 and the available stock; prices must be greater than zero; cancelled orders restore stock exactly once.
- Success and error messages are shown for every action.
- A product that already has orders cannot be deleted (`PROTECT`), preserving order history.

**Frontend**
- Pages: `/products/` (catalog), `/products/add/`, `/products/<id>/edit/`, `/products/<id>/delete/`, `/products/checkout/<id>/`, `/products/orders/`, `/products/orders/<id>/status/`.
- Both role dashboards link to the feature.

**Access rules**
- All feature pages require login.
- Customers only see their own orders and can only cancel their own pending orders or delete their own cancelled orders.
- Only admins can create/edit/delete products or change order statuses.
- All customer-created orders are linked to the logged-in user through `Order.user`.

## Standard Features (PD1)

- Account registration and validation
- Login / logout
- Role-based dashboard (`admin` vs `customer`)
- View and edit user profile (including profile photo)

## Tech Stack

- Python 3.9+, Django 4.2
- PostgreSQL (Supabase) via `psycopg2-binary`
- `python-dotenv` for environment variables

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/cardenas-469/EzyTech-Cardenas-PeterMartin-G2.git
   cd EzyTech-Cardenas-PeterMartin-G2
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root (never commit it):
   ```env
   SECRET_KEY=your-django-secret-key
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_HOST=your_database_host
   DB_PORT=5432
   ```
   A template is available in `.env.example`.

5. Apply migrations:
   ```bash
   python manage.py migrate
   ```

6. (Optional) Load sample products for a quick demo:
   ```bash
   python manage.py loaddata sample_products
   ```

7. Create an admin account if you do not have one:
   ```bash
   python manage.py createsuperuser
   ```

8. Run the development server:
   ```bash
   python manage.py runserver
   ```
   Open http://127.0.0.1:8000/.

## Test Accounts (Supabase development database)

| Role | Username | Password |
|---|---|---|
| Admin | `admin.test` | `EzyTechAdmin2026!` |
| Customer | `customer.test` | `EzyTechCustomer2026!` |

> These are development-only accounts. Change or remove them before any public deployment.

## Running Tests

Supabase's connection pooler does not support Django's test-database creation, so tests use a separate in-memory SQLite settings module:

```bash
python manage.py test --settings=config.settings_test
```

Current suite: 25 tests covering catalog access, product CRUD permissions, validation, checkout/stock deduction, order isolation, cancellation, deletion, status transitions, and stock restoration.

## Branching Workflow

- `main` – stable, merged releases only
- `develop` – integration branch
- `feature/product-catalog` – catalog + checkout vertical slice (merged to `develop` via PR #1)
- `feature/product-catalog-fixes` – catalog hardening, validation, CRUD, role access, tests (PR into `develop`)
- `feature/order-management` – order cancellation/status management (PR into `develop`)

Increment PRs: feature branches → `develop`; then `develop` → `main`.

## Project Documentation

- `docs/EzyTech-Cardenas-PeterMartin-G2-PD2.pdf` – PD2 completion report
- `docs/PD2-Completion-Report.md` – editable source of the report
