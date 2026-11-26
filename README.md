# EzyTech – Project Development 3 (PD3)

EzyTech is a Django + PostgreSQL e-commerce platform for technology products. This repository contains the Account feature from Project Development 1, the PD2 core feature (**Product Catalog & Order Management**), and the PD3 hardening work that makes the feature reliable, secure, and tested.

## Hardening (PD3)

PD3 does not add new features. It hardens the existing vertical slice:

- **Validation:** every core form validates on the server (quantity vs. stock, positive price, unique product name, contact number format, case-insensitive unique e-mail, and profile-photo type/size).
- **Error handling:** custom 403, 404, and 500 pages replace Django debug pages; invalid IDs use `get_object_or_404`.
- **Configuration:** `DEBUG`, `ALLOWED_HOSTS`, and optional HTTPS flags are read from `.env`; secrets never live in code.
- **Access control:** all core views require login, roles are enforced in the view, and customers cannot read or modify another customer's order by changing the URL.
- **CSRF and methods:** every POST form includes `{% csrf_token %}`; cancel, delete, and status changes are POST-only and use confirmation pages or dialogs.
- **Data integrity:** unique product names, database check constraints for prices/totals/quantities/stock, `transaction.atomic()` around multi-step saves, row locking so stock is restored exactly once, `PROTECT`/`SET_NULL`/`CASCADE` on foreign keys, and `select_related` on order lists.


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
- Pages: `/products/` (catalog), `/products/add/`, `/products/<id>/edit/`, `/products/<id>/delete/`, `/products/checkout/<id>/`, `/products/orders/`, `/products/orders/<id>/` (detail), `/products/orders/<id>/status/`.
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
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_HOST=your_database_host
   DB_PORT=5432
   ```
   A template is available in `.env.example`. Set `DEBUG=False` and configure
   `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE` in
   production.

5. Apply migrations:
   ```bash
   python manage.py migrate
   ```

6. (Optional) Load sample products for a quick demo:
   ```bash
   python manage.py seed_products
   ```
   The command links the demo products to an admin account. Pass
   `--admin <username>` to choose a specific admin. It also repairs any
   existing product that has no owner.

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

Supabase's connection pooler does not support Django's test-database creation, so `manage.py test` automatically switches to an in-memory SQLite database. The application itself always uses PostgreSQL/Supabase. You can also run the explicit test settings module:

```bash
python manage.py test
# or
python manage.py test --settings=config.settings_test
```

Current suite: 74 tests. It covers registration/login/profile validation, role dashboards, catalog access, product CRUD permissions, duplicate product names, database constraints, checkout/stock deduction, order isolation, cross-user access blocking, CSRF enforcement, POST-only actions, invalid IDs, custom error pages, cancellation/deletion stock restoration, status transitions, filtering/search, dashboard statistics, and profile-photo validation.

## Branching Workflow

- `main` – stable, merged releases only
- `develop` – integration branch
- `fix/iss-02-sample-data` – replaces the ownerless sample fixture with a management command (PR #10)
- `hardening/config-and-errors` – env-driven debug settings, custom error pages, security headers, account validation (PR #11)
- `hardening/data-integrity` – unique names, database check constraints, row locking (PR #12)
- `test/core-hardening` – authentication, CSRF, access-control, constraint, and URL tests (PR #13)
- `docs/pd3-report` – completed official PD3 report and evidence screenshots (PR #14)

Increment PRs: work branches → `develop`; then `develop` → `main`.

## Project Documentation

- `docs/EzyTech-Cardenas-PeterMartin-G2-PD3.pdf` – completed official PD3 hardening report
- `docs/EzyTech-Cardenas-PeterMartin-G2-PD3.docx` – editable PD3 report source
- `docs/EzyTech-Cardenas-PeterMartin-G2-PD2.pdf` – completed official PD2 report with user-flow screenshots
- `docs/EzyTech-Cardenas-PeterMartin-G2-PD2.docx` – editable PD2 report source
- `docs/screenshots/` – PD2 user-flow screenshots plus PD3 validation, blocked-access, 404, and test-output evidence
