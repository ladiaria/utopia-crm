# 2025-10-30: Product Model and Subscription Form Fixes

## Summary

Fixed critical issues with product `target_product` field configuration and resolved mutual exclusivity problems between digital and weekday subscription products in the new subscription form. These changes prevent incorrect discount products from being added and ensure proper price calculations.

## Key Improvements

### 1. Product Model: Fixed `target_product` Field Configuration

**Problem:** The `target_product` field had `limit_choices_to={"offerable": True, "type": "S"}`, which prevented bundle products (like "la-diaria-2-dias") from appearing in the dropdown. Bundle products are created by price rules and have `offerable=False` by design, making it impossible to set them as target products for discount products.

**Impact:** This caused discount products to have `target_product=NULL`, which led to incorrect price rule processing where discount products were counted as regular products instead of being properly excluded.

**Solution:** Changed the `limit_choices_to` filter to use `active` instead of `offerable`.

**File:** `core/models.py`

**Changes:**

```python
# Before
target_product = models.ForeignKey(
    "self",
    blank=True,
    null=True,
    on_delete=models.SET_NULL,
    limit_choices_to={"offerable": True, "type": "S"},  # Too restrictive!
    verbose_name=_("Target product"),
)

# After
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

**Benefits:**

- ✅ **Bundle products now appear** in the `target_product` dropdown
- ✅ **Discount products can be properly configured** to target bundle products
- ✅ **Price rules work correctly** - discount products are excluded from pool calculations
- ✅ **Better help text** explains the field's purpose
- ✅ **More logical filter** - active products are what matters, not offerability

**Migration Required:** Yes, but metadata-only (changes `limit_choices_to`), no data changes.

---

### 2. Product Admin: Improved `target_product` UX

**Problem:** The `target_product` field used a dropdown which could be confusing and hard to use, especially when the filtered list was empty or when trying to see the current value.

**Solution:** Added `raw_id_fields` for better visibility and updated admin comment.

**File:** `core/admin.py`

**Changes:**

```python
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Before: TODO comment about validations
    # Note: target_product is limited to active subscription products (type='S')
    # and is primarily used for discount products to specify which product they discount

    # ... existing fields ...

    raw_id_fields = ("target_product",)  # Makes it easier to see and set the value
```

**Benefits:**

- ✅ **Clearer interface** - Shows a search widget instead of dropdown
- ✅ **Better visibility** - Easy to see the current target product ID
- ✅ **Easier to set** - Can directly enter product IDs
- ✅ **Updated documentation** - Comment explains the field's purpose

---

### 3. Subscription Form: Digital and Weekday Product Mutual Exclusivity

**Problem:** When users selected weekday products (lunes-viernes) and then clicked digital, or vice versa, several issues occurred:

1. Products were unchecked but green borders remained
2. Discount products stayed visible
3. **Price calculation was wrong** - showed the sum of both digital and weekday products
4. The form state was inconsistent

**Root Cause:** The price calculation function `loadDynamicPrices()` in `static/js/product_dynamic_prices.js` fires immediately on checkbox click, reading all checked checkboxes before our mutual exclusivity logic could uncheck the conflicting products.

**Solution:** Implemented a comprehensive mutual exclusivity system with proper timing control.

**File:** `utopia_crm_ladiaria/templates/ladiaria_new_subscription.html`

**Implementation:**

#### Step 1: Flag to Control Timing

```javascript
// Flag to prevent activateSend and loadDynamicPrices during mutual exclusivity logic
var isProcessingMutualExclusivity = false;
```

#### Step 2: Wrap Price Calculation Functions

```javascript
// Wrap activateSend to respect the flag
var originalActivateSend = window.activateSend || activateSend;
window.activateSend = activateSend = function() {
  if (!isProcessingMutualExclusivity) {
    originalActivateSend();
  }
};

// Wrap loadDynamicPrices to respect the flag (THE KEY FIX!)
if (typeof loadDynamicPrices !== 'undefined') {
  var originalLoadDynamicPrices = loadDynamicPrices;
  window.loadDynamicPrices = loadDynamicPrices = function() {
    if (!isProcessingMutualExclusivity) {
      originalLoadDynamicPrices();
    }
  };
}
```

#### Step 3: When Digital is Selected

```javascript
$(".la_diaria_digital").change(function(){
  if($(".la_diaria_digital").is(":checked")){
    isProcessingMutualExclusivity = true;  // Block price calculations

    // Uncheck all weekday products
    $(".la_diaria_product").each(function() {
      if ($(this).is(":checked")) {
        $(this).prop("checked", false).removeAttr("checked");
        // Manually update the styling without triggering change
        $(this).closest('.border').removeClass('bg-success-light').addClass('bg-light');
      }
    });

    // Hide and uncheck all weekday-related discount products
    $(".descuento5dias, .descuento3dias, .descuento2dias").each(function() {
      if ($(this).is(":checked")) {
        $(this).prop("checked", false).removeAttr("checked");
        $(this).closest('.border').removeClass('bg-success-light').addClass('bg-light');
      }
    });
    $(".descuento5dias, .descuento3dias, .descuento2dias").addClass("d-none");

    // Trigger discount visibility update once at the end
    updateDiscountVisibility();

    // Use setTimeout to ensure DOM updates are complete before recalculating
    setTimeout(function() {
      isProcessingMutualExclusivity = false;  // Re-enable price calculations
      if (typeof originalLoadDynamicPrices !== 'undefined') {
        originalLoadDynamicPrices();  // Calculate price with correct checkbox states
      }
      originalActivateSend();
    }, 50);
  }
});
```

#### Step 4: When Weekday Product is Selected

```javascript
$(".la_diaria_product").change(function(){
  if($(".la_diaria_product").is(":checked")){
    isProcessingMutualExclusivity = true;  // Block price calculations

    // Uncheck digital product without triggering cascading events
    if ($(".la_diaria_digital").is(":checked")) {
      $(".la_diaria_digital").prop("checked", false).removeAttr("checked");
      // Manually update the styling
      $(".la_diaria_digital").closest('.border').removeClass('bg-success-light').addClass('bg-light');
    }

    // Trigger discount visibility update
    updateDiscountVisibility();

    // Use setTimeout to ensure DOM updates are complete before recalculating
    setTimeout(function() {
      isProcessingMutualExclusivity = false;  // Re-enable price calculations
      if (typeof originalLoadDynamicPrices !== 'undefined') {
        originalLoadDynamicPrices();  // Calculate price with correct checkbox states
      }
      originalActivateSend();
    }, 50);
  }
});
```

**How It Works:**

1. **User clicks digital** → `isProcessingMutualExclusivity = true`
2. **Click event fires** → `loadDynamicPrices()` tries to run → **BLOCKED by flag** ✅
3. **We uncheck weekday products** silently (no events)
4. **We update styling** manually (green borders removed)
5. **We hide discount products** for weekday bundles
6. **After 50ms:**
   - Reset flag: `isProcessingMutualExclusivity = false`
   - Manually call `originalLoadDynamicPrices()` with correct checkbox states
   - Call `originalActivateSend()` to update form validation

**Key Technical Details:**

- **`.prop("checked", false)`** - Updates the JavaScript property
- **`.removeAttr("checked")`** - Removes the HTML attribute (ensures form sees it as unchecked)
- **`.closest('.border').removeClass('bg-success-light').addClass('bg-light')`** - Manually updates styling
- **`setTimeout(..., 50)`** - Gives the browser time to process DOM changes
- **Wrapper functions** - Intercept price calculation calls during the transition period

**Benefits:**

- ✅ **Correct price calculation** - Only checked products are sent to the server
- ✅ **Visual consistency** - Green borders update correctly
- ✅ **Proper discount handling** - Weekday discounts hide when digital is selected
- ✅ **Clean form state** - No lingering checked attributes
- ✅ **No race conditions** - Flag prevents premature calculations

---

## Technical Details

### Files Modified

1. **core/models.py**
   - Changed `Product.target_product` field's `limit_choices_to` filter
   - Added help text

2. **core/admin.py**
   - Added `raw_id_fields = ("target_product",)` to `ProductAdmin`
   - Updated comment documentation

3. **utopia_crm_ladiaria/templates/ladiaria_new_subscription.html**
   - Added mutual exclusivity flag system
   - Wrapped `activateSend()` and `loadDynamicPrices()` functions
   - Enhanced digital/weekday product change handlers
   - Added proper timing control with setTimeout

### Related Files (Context)

- **static/js/product_dynamic_prices.js** - Contains the `loadDynamicPrices()` function that calculates prices via AJAX
- **support/views/all_views.py** - Contains `api_dynamic_prices()` endpoint that processes products and returns prices
- **core/utils.py** - Contains `process_products()` function that applies price rules

### Browser Compatibility

All JavaScript changes use standard ES5 syntax and jQuery, ensuring compatibility with:

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

### Performance Impact

- **Minimal**: Only client-side JavaScript changes
- **50ms delay**: Intentional to ensure DOM updates complete
- **No additional HTTP requests**: Same AJAX call, just better timing
- **Improved UX**: Prevents multiple rapid price calculations

## Debugging Tools Created

To help diagnose the `target_product` issue, several debugging tools were created in `utopia-crm-ladiaria`:

1. **debug_detailed_trace.py** - Step-by-step trace of `process_products()` function
2. **debug_specific_issue.py** - Quick check for specific product combinations
3. **compare_products_and_rules.py** - Compare products and price rules
4. **fix_product_96_target.py** - Interactive script to fix product target_product values
5. **INVESTIGATION_CHECKLIST.md** - Complete troubleshooting guide

These tools can be reused for future similar issues.

## Migration Notes

### Database Migration Required

Yes, for the `Product` model change:

```bash
cd /path/to/utopia-crm
python manage.py makemigrations core -n change_target_product_limit_choices
python manage.py migrate
```

**Note:** This is a metadata-only migration (changes `limit_choices_to`), so it won't affect existing data.

### Data Fixes Required

If you have discount products with `target_product=NULL` that should point to bundle products:

```python
python manage.py shell
```

```python
from core.models import Product

# Example: Fix "descuento-parcial-2-dias" to target "la-diaria-2-dias"
discount = Product.objects.get(slug="descuento-parcial-2-dias-50-3-meses-retencion")
target = Product.objects.get(slug="la-diaria-2-dias")

discount.target_product = target
discount.save()

print(f"✅ Fixed! {discount.name} now targets {target.name}")
```

## Testing Recommendations

### 1. Product Admin Testing

- [ ] Open Product admin in Django admin
- [ ] Edit a discount product (type='D' or 'P')
- [ ] Verify `target_product` field shows a search widget (not dropdown)
- [ ] Verify bundle products (like "la-diaria-2-dias") appear in search results
- [ ] Set a bundle product as target and save
- [ ] Verify it saves correctly

### 2. Subscription Form Testing

#### **Test Case 1: Digital → Weekday**

- [ ] Open new subscription form
- [ ] Select lunes + martes
- [ ] Verify price shows 2-day bundle price (e.g., 880)
- [ ] Verify green borders on lunes and martes
- [ ] Click digital
- [ ] **Verify lunes and martes uncheck**
- [ ] **Verify green borders disappear from lunes and martes**
- [ ] **Verify price shows only digital price (e.g., 352)**
- [ ] **Verify 2-day discount hides**

#### **Test Case 2: Weekday → Digital**

- [ ] Open new subscription form
- [ ] Select digital
- [ ] Verify price shows digital price
- [ ] Verify green border on digital
- [ ] Click lunes
- [ ] **Verify digital unchecks**
- [ ] **Verify green border disappears from digital**
- [ ] **Verify price shows only lunes price**

#### **Test Case 3: Multiple Weekdays**

- [ ] Select lunes + martes + miércoles
- [ ] Verify price shows 3-day bundle price
- [ ] Verify 3-day discount appears
- [ ] Click digital
- [ ] **Verify all weekday products uncheck**
- [ ] **Verify all green borders disappear**
- [ ] **Verify 3-day discount hides**
- [ ] **Verify price shows only digital**

#### **Test Case 4: With Discounts**

- [ ] Select lunes + martes
- [ ] Select a 2-day discount
- [ ] Verify price includes discount
- [ ] Click digital
- [ ] **Verify weekday products and discount uncheck**
- [ ] **Verify price shows only digital (no discount)**

### 3. Price Rule Testing

- [ ] Test that discount products with proper `target_product` are excluded from pool calculations
- [ ] Verify bundle products are created correctly (e.g., lunes + martes → 2 días)
- [ ] Verify discount products are added only when their target product is present

### 4. Cross-browser Testing

- [ ] Test in Chrome
- [ ] Test in Firefox
- [ ] Test in Safari
- [ ] Test on mobile devices
- [ ] Verify timing works correctly in all browsers

## Future Enhancements

- Consider adding visual feedback during the 50ms transition period
- Add unit tests for the mutual exclusivity logic
- Consider making the timeout configurable
- Add analytics to track how often users switch between digital and weekday products
- Consider adding a warning message when switching product types

## Related Issues

This fix resolves the following issues:

1. **Discount products not appearing in admin** - Fixed by changing `limit_choices_to`
2. **Incorrect price calculations** - Fixed by wrapping `loadDynamicPrices()`
3. **Visual inconsistencies** - Fixed by manual styling updates
4. **Race conditions in form state** - Fixed by timing control flag

## Documentation

- Updated `Product` model field help text
- Updated `ProductAdmin` comment
- Created comprehensive debugging tools and guides
- This changelog documents the complete solution

---

**Author:** Cascade AI Assistant
**Date:** 2025-10-30
**Severity:** High (affects price calculations and data integrity)
**Breaking Changes:** None (backward compatible)
**Migration Required:** Yes (metadata-only)
