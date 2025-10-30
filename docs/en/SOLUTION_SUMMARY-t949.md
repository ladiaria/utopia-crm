# Solution: Product 102 Being Added Incorrectly

## Problem Identified

Product 102 (`Descuento por cantidad hasta 2`) was being added in **dev** but not in **production** when processing products `{43, 44, 96}`.

## Root Cause

**Product 96** (`Descuento parcial 2 dias 50% 3 meses retención`) had different `target_product` values:

- **Dev**: `target_product = NULL` ❌
- **Production**: `target_product = 50` (la-diaria-2-dias) ✅

### Why This Matters

The `process_products` logic (lines 505-506 in `core/utils.py`):

```python
if input_product.type in "DP" and input_product.target_product:
    temporary_exclude_list.append(input_product.target_product)
```

**When `target_product` is set:**

- The target product gets excluded from pool calculations
- Prevents rules from counting it
- Production behavior: Adjusted length = 0, rule doesn't trigger

**When `target_product` is NULL:**

- The discount product itself gets added to the pool
- Counts as a regular product
- Dev behavior: Adjusted length = 2, rule triggers and adds product 102

## Changes Made

### 1. Fixed `limit_choices_to` Filter

**File:** `/Users/tanyatree/git/utopia-crm/core/models.py`

**Before:**

```python
target_product = models.ForeignKey(
    "self",
    blank=True,
    null=True,
    on_delete=models.SET_NULL,
    limit_choices_to={"offerable": True, "type": "S"},  # Too restrictive!
    verbose_name=_("Target product"),
)
```

**After:**

```python
target_product = models.ForeignKey(
    "self",
    blank=True,
    null=True,
    on_delete=models.SET_NULL,
    limit_choices_to={"active": True, "type": "S"},  # Fixed!
    verbose_name=_("Target product"),
    help_text=_("The subscription product this discount applies to. Only active subscription products are shown."),
)
```

**Why:** Bundle products (like product 50 "la-diaria-2-dias") are **not offerable** by design - they're created by price rules. The old filter prevented them from appearing in the `target_product` dropdown.

### 2. Added `raw_id_fields` to Admin

**File:** `/Users/tanyatree/git/utopia-crm/core/admin.py`

```python
class ProductAdmin(admin.ModelAdmin):
    raw_id_fields = ("target_product",)  # Makes it easier to see and set the value
```

**Why:** The dropdown was confusing and hard to use. The raw ID field shows a search widget that makes it clearer what value is set.

### 3. Updated Admin Comment

Changed the TODO comment to a proper note explaining the field's purpose.

## How to Fix Data

### Option 1: Use the Fix Script

```bash
cd /Users/tanyatree/git/utopia-crm-ladiaria
python fix_product_96_target.py
```

### Option 2: Manual Fix in Shell

```python
python manage.py shell
```

```python
from core.models import Product

p96 = Product.objects.get(id=96)
p50 = Product.objects.get(id=50)

p96.target_product = p50
p96.save()

print("✅ Fixed!")
```

### Option 3: Fix in Admin

1. Go to Product admin
2. Edit product 96
3. In the `target_product` field, enter "50"
4. Save

## Verification

After fixing, run the detailed trace:

```bash
cd /Users/tanyatree/git/utopia-crm-ladiaria
python debug_detailed_trace.py
```

You should see:

```text
RULE Priority 5: Descuento por cantidad hasta 2
  Mode: 3, Wildcard: pool_or_any
  Amount to pick: 2 (eq)
    Excluding target: 50 (from discount 96)
    Excluded product 50 already in output, incrementing ignore counter
  Products in pool: 0
  Non-discount added so far: 1
  Non-discount to ignore: 1
  Adjusted length (pool_or_any): 0 + 1 - 1 = 0
  ❌ Condition NOT met: 0 vs 2 (eq)
```

Product 102 will **NOT** be added! ✅

## Migration Required

After making the model change, create and run a migration:

```bash
cd /Users/tanyatree/git/utopia-crm
python manage.py makemigrations core -n change_target_product_limit_choices
python manage.py migrate
```

**Note:** This is a metadata-only change (changes `limit_choices_to`), so it won't affect existing data. It only changes which products appear in the admin dropdown.

## Lessons Learned

1. **`limit_choices_to` affects admin UX**: If products don't appear in dropdowns, check this filter
2. **Data inconsistencies are hard to spot**: Even "identical" databases can have subtle field differences
3. **Detailed tracing is essential**: The step-by-step trace immediately revealed the issue
4. **Bundle products aren't offerable**: Products created by price rules typically have `offerable=False`

## Files Modified

- `/Users/tanyatree/git/utopia-crm/core/models.py` - Fixed `limit_choices_to` filter
- `/Users/tanyatree/git/utopia-crm/core/admin.py` - Added `raw_id_fields`, updated comment

## Debug Tools Created

All in `/Users/tanyatree/git/utopia-crm-ladiaria/`:

- `debug_detailed_trace.py` - Step-by-step trace of `process_products`
- `debug_specific_issue.py` - Quick check for the specific issue
- `compare_products_and_rules.py` - Compare products and rules
- `fix_product_96_target.py` - Interactive script to fix product 96
- `INVESTIGATION_CHECKLIST.md` - Complete troubleshooting guide
- `QUICK_DEBUG.md` - Quick reference

These tools can be reused for future similar issues!
