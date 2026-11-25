# Billing priority: a fixed tie-break, and no ties between billing products

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#167
- **Type:** Bug Fix / Data Integrity
- **Component:** core (Product, Subscription)
- **Impact:** Billing, logistics, and anyone editing products in the admin

## 🎯 Summary

Billing takes the address, the route and the delivery order of each invoice from one product of the subscription: the one returned by `Subscription.get_first_product_by_priority()`, the subscription or other product with the lowest `billing_priority`. The invoice name does not come from it: it is the subscription's billing name or the contact's name.

The query ordered only by `billing_priority`. When two products of a subscription had the same number, the database returned either of them, and nothing guaranteed it would return the same one on the next night. It surfaced in production on 2026-11-24 with subscription 137634: Gigantes (priority 10, route 99) and Revista Crucigramas (priority 10, no route). The magazine won the tie, so the subscription had no route and had not been billed since 2026-01-02. In production two pairs of active products tied (priorities 1 and 10).

Two changes: the queries now break ties in a fixed way, and the product form no longer lets two active billing products share a priority.

## ✨ Changes

### 1. A fixed tie-break in every query by billing priority

**File:** `core/models.py`

The new `Product.billing_priority_order(prefix="")` returns the ordering billing uses: `billing_priority` with NULLs last, then the product id.

```python
return (F(f"{prefix}billing_priority").asc(nulls_last=True), f"{prefix}id")
```

It is used by `get_first_product_by_priority()` and by `get_full_address_by_priority()`, `get_address_by_priority()` and `get_address_2_by_priority()`, which also walked the products by priority without a tie-break.

- **Ties:** the product with the lowest id wins, always the same one.
- **NULLs last, explicitly:** PostgreSQL already sorts NULL last in ascending order, but MySQL and MariaDB sort it first. Without `nulls_last=True`, on those databases a product without priority would win over every product with a number.

`get_first_product_by_priority()` keeps returning `None` when the subscription has no subscription or other product. The new `Product.BILLING_TYPES` names those two types.

### 2. Two active billing products cannot share a priority

**File:** `core/models.py`

`Product.clean_fields()` rejects an active product of type subscription or other whose `billing_priority` is already used by another active product of those types. The message names the other product and its id. An empty priority is allowed, and so are inactive products, newsletters and discounts.

- **Only when it changes:** the check runs for a new product, or when its priority, type or active flag differ from the saved ones (`billing_priority_changed()`). The ties saved before this rule therefore do not block editing the other fields of those products. They still have to be fixed by hand.
- **Forms without the field:** the admin product list edits some columns in place, but not the priority. Changing a product's type there can still create a tie. A field error for a field the form does not have would raise `ValueError`, so in that case the error is a non-field one. This is the pattern the Django documentation gives for `clean_fields()`.

`billing_priority_tie()` returns the other product, or `None`. A customization package can use it, together with `BILLING_TYPES`, to list ties.

### 3. Spanish translation

**File:** `locale/es/LC_MESSAGES/django.po`

The new message was added by hand. `makemessages` would have rewritten the whole file, with shifted line references and other untranslated strings.

## 📁 Files Modified

- **`core/models.py`** — `Product.BILLING_TYPES`, `billing_priority_order()`, `billing_priority_tie()`, `billing_priority_changed()`, `clean_fields()`; the four `*_by_priority` methods of `Subscription` use the new order
- **`locale/es/LC_MESSAGES/django.po`** — Translation of the validation message
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`tests/test_product_billing_priority.py`** — Tie-break by id, NULLs last, only subscription and other products count, addresses use the same order, and the validation (new, changed, activated, allowed cases, saved tie, form without the field)

## 🧪 Manual Testing

1. **Tie rejected:** in the admin, open an active subscription product and set the priority of another active subscription product. **Verify:** the form comes back with an error under «Billing priority» naming the other product and its id.
2. **Empty priority allowed:** clear the priority and save. **Verify:** it saves.
3. **Edge case, saved tie:** with two active products that already share a priority (as in production before fixing them), change the price of one of them. **Verify:** it saves, with no error.
4. **Edge case, admin list:** in the product list, change the type of a newsletter that has the priority of an active subscription product to «Subscription» and save. **Verify:** the row comes back with the error, and the page does not crash.
5. **Billing:** on a subscription with two products that share a priority, `subscription.get_first_product_by_priority()` returns the one with the lower id every time.

## 📝 Deployment Notes

- No database migrations required, no settings.
- **The production ties stay until someone fixes them:** `la-diaria-lunes` and `modragon-full` at 1, `gigantes` and `revista-crucigramas` at 10 (2026-11-24). After the deploy, billing picks the lower id in each pair: `la-diaria-lunes` and `gigantes`.
- Merge this before the `utopia-crm-ladiaria` side of the same issue (a view of the priorities). That view does not import anything new from here, but it says ties go to the lowest id, which is only true after this deploy.

## 🎓 Design Decisions

- **Why validate only on change:** validating on every save would have blocked editing any field of the four tied products until the ties were fixed, and one of them waits for a business decision. The rule only needs to stop new ties.
- **Why `clean_fields()` and not `clean()`:** `clean()` does not receive `exclude`, so it cannot tell when the form has no priority field. `clean_fields()` does, and turns the error into a non-field one.
- **The validation runs only in forms:** like any model validation in Django, `Product.objects.create()` and `save()` do not call it. Products are edited in the admin, so that is enough.
- **Inactive products are not checked**, as the issue asks. `get_first_product_by_priority()` does not filter by active, so an inactive product still on subscriptions would still compete. On 2026-11-25 no inactive product tied with an active one.

---

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl167-prioridad-facturacion
- **Type:** Bug Fix / Data Integrity
- **Modules affected:** core
