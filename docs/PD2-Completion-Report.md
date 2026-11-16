# Project Development 2 – Completion Report

**System Name:** EzyTech  
**Student:** Cardenas, Peter Martin  
**Section:** G2  
**Course:** Project Development 2  
**Date:** November 16, 2026  
**Repository:** https://github.com/cardenas-469/EzyTech-Cardenas-PeterMartin-G2

## 1. Project Overview

EzyTech is a Django + PostgreSQL e-commerce platform for technology products. Project Development 1 delivered the account and role features. Project Development 2 adds the approved core feature — **Product Catalog & Order Management** — as a complete vertical slice from the database to the user interface.

## 2. Features Implemented

### 2.1 Standard Features (PD1) – still working

| Feature | Status | Notes |
|---|---|---|
| Account Registration | Complete | Custom user model, unique email, password validation, success/error messages |
| Login / Logout | Complete | Django authentication, protected routes, POST logout |
| Role-Based User Dashboard | Complete | Separate admin and customer dashboards with live statistics |
| User Profile | Complete | View and edit name, email, contact number, and profile photo |

### 2.2 Core Feature (PD2) – Product Catalog & Order Management

**Database**
- `Product` model: name, description, price, stock, `created_by` (FK to `User`), created timestamp.
- `Order` model: `user` (FK to `User`), `product` (FK to `Product`, `PROTECT`), quantity, total price, status, created timestamp.
- Migrations committed and applied to PostgreSQL/Supabase.
- Status flow: Pending → Confirmed → Shipped → Completed; Pending/Confirmed can be cancelled.

**Backend**
- Product list/search, create, update, and delete.
- Checkout with validation, stock deduction, and order creation.
- Order history with status filtering and search.
- Order detail page, cancellation, deletion, and admin status updates.
- Docker-free Django views, ModelForms, and URL routes.

**Frontend**
- Django templates for the catalog, product form, delete confirmation, checkout, order history, order detail, and status update.
- Success and error messages on every action.
- Role-aware navigation and dashboard links.

**CRUD coverage**
| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| Product | Admin | All logged-in users | Admin | Admin (blocked when orders exist) |
| Order | Customer checkout | Owner or admin | Status: admin; cancel: owner | Owner (cancelled only) or admin |

**Validation and business rules**
- Quantity must be at least 1 and cannot exceed available stock.
- Price must be greater than zero; product name at least 3 characters; stock cannot be negative.
- Checkout uses `transaction.atomic()` + `select_for_update()` to prevent overselling.
- Cancelling or deleting an active order restores stock exactly once.
- Cancelled orders already have stock restored; completed sales keep their stock deduction.
- Products with order history cannot be deleted, preserving records.
- Invalid status transitions are rejected.

**Account integration and role-based access**
- Every feature page requires login.
- Orders are linked to the logged-in user via `Order.user`.
- Customers only see and manage their own orders.
- Only admins can create/edit/delete products or change order statuses.
- Feature links appear on the correct role dashboard.

## 3. Branches and Pull Requests

| Branch | Purpose | Pull Request | Result |
|---|---|---|---|
| `feature/product-catalog` | Catalog + checkout vertical slice | PR #1 → `develop` | Merged |
| `feature/product-catalog-fixes` | Fix catalog crash, product CRUD, validation, role access, tests | PR #3 → `develop` | Merged |
| `feature/order-management` | Order detail, filtering/search, dashboard statistics, account tests | PR #4 → `develop` | Merged |
| `develop` → `main` | Final PD2 increment | PR #5 | Merged |

Merged feature branches were kept. `main` only receives merged release PRs.

## 4. Testing Summary

- **42 automated tests pass** using `python manage.py test --settings=config.settings_test`.
- Coverage includes registration, login, profile updates, role dashboards, product CRUD permissions, validation, checkout, stock deduction, order isolation, cancellation, deletion, status transitions, stock restoration, order detail access, filtering, search, and dashboard statistics.
- Manual smoke test performed on PostgreSQL/Supabase for catalog, product management, checkout, order detail, filters, and both dashboards.

## 5. Remaining Tasks

All PD2 requirements are complete. Optional future work:
- Payment gateway integration
- Multi-item shopping cart and checkout
- Email/SMS order notifications
- Order receipt printing/export
- Product images and categories
- Production deployment hardening (environment-specific settings, allowed hosts, static files)

## 6. Outstanding Issues

- Supabase's connection pooler does not support Django's test-database creation. Tests therefore use an in-memory SQLite settings module (`config.settings_test`), while the application itself uses PostgreSQL/Supabase. This is documented in the README.
- The optional `sample_products` fixture creates catalog seed data without a `created_by` user because it is system-provided. Products created through the admin UI are linked to the admin who created them.
- Checkout is single-product per order, matching the approved scope; a multi-item cart is future work.
- Development test accounts must be rotated or removed before public deployment.

## 7. Test Accounts

| Role | Username | Password |
|---|---|---|
| Admin | `admin.test` | `EzyTechAdmin2026!` |
| Customer | `customer.test` | `EzyTechCustomer2026!` |

## 8. Repository Links

- Repository: https://github.com/cardenas-469/EzyTech-Cardenas-PeterMartin-G2
- Pull requests: https://github.com/cardenas-469/EzyTech-Cardenas-PeterMartin-G2/pulls?q=is%3Apr
- Report PDF: `docs/EzyTech-Cardenas-PeterMartin-G2-PD2.pdf`
