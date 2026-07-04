# Issue Next Action Date Automation and Filtering Enhancement

**Date:** 2026-01-21
**Type:** Feature Enhancement & Automation
**Component:** Issue Management System
**Impact:** User Experience, Workflow Automation, Data Quality

## Summary

Comprehensive enhancement of the issue management system with automatic next_action_date setting when status changes, advanced filtering capabilities for both issue date and next action date, and sortable table columns. These changes significantly improve workflow efficiency by automating follow-up scheduling and providing powerful filtering tools for issue tracking.

## Motivation

The issue management system is critical for tracking customer issues and ensuring timely follow-ups. The previous implementation had several limitations:

1. **Manual Date Management:** Users had to manually set next_action_date when changing issue status, leading to forgotten follow-ups
2. **Limited Filtering:** No ability to filter issues by next action date, making it difficult to find upcoming tasks
3. **No "Next 7 Days" Option:** Common use case for finding upcoming work wasn't supported
4. **Unclear Date Fields:** Users were confused about the difference between "Date" and "Next Action Date"
5. **No Sorting:** Couldn't sort issues by date or next action date to prioritize work
6. **Poor Layout:** Date filters weren't organized efficiently in the UI

## Key Features Implemented

### 1. Automatic Next Action Date Setting on Status Change

**File:** `support/views/all_views.py`

**Problem:**
When users changed an issue's status, they often forgot to set a next_action_date, resulting in issues falling through the cracks without scheduled follow-ups.

**Solution:**
Added `form_valid()` method to `IssueDetailView` that automatically sets next_action_date to tomorrow when:

- Issue status changes, AND
- next_action_date is missing (None), OR
- next_action_date is today or in the past

**Implementation:**

```python
def form_valid(self, form):
    """
    Override form_valid to automatically set next_action_date when status changes.
    If status has changed and next_action_date is missing or in the past, set it to tomorrow.
    """
    issue = self.get_object()
    old_status = issue.status

    # Let the form save normally first
    response = super().form_valid(form)

    # Check if status has changed
    new_status = self.object.status
    if old_status != new_status:
        # Check if next_action_date needs to be updated
        today = date.today()
        if not self.object.next_action_date or self.object.next_action_date <= today:
            # Set next_action_date to tomorrow
            self.object.next_action_date = today + timedelta(days=1)
            self.object.save(update_fields=['next_action_date'])

    return response
```

**Benefits:**

- **Prevents Lost Follow-ups:** Ensures every status change has a scheduled next action
- **Smart Logic:** Only updates when needed (missing or past dates)
- **Respects Future Dates:** Doesn't override manually set future dates
- **Automatic Workflow:** Reduces manual data entry and human error
- **Efficient:** Uses `update_fields` to only update the necessary field

**Use Cases:**

1. **Status Change from "Open" to "In Progress":** Automatically schedules follow-up for tomorrow
2. **Reopening Closed Issue:** Sets next action date if previous date was in the past
3. **Escalation:** When changing status to escalated, ensures timely follow-up
4. **Manual Override:** Users can still set custom future dates that won't be changed

### 2. Advanced Next Action Date Filtering

**File:** `support/filters.py`

**Problem:**
Users couldn't filter issues by next_action_date, making it impossible to find:

- Issues due today
- Issues due in the next 7 days
- Overdue issues (past next action dates)
- Issues scheduled for specific date ranges

**Solution:**
Added comprehensive next_action_date filtering with the same options as issue date filtering.

**Implementation:**

```python
class IssueFilter(django_filters.FilterSet):
    # Issue Date filters with helper text
    date = django_filters.ChoiceFilter(
        choices=CREATION_CHOICES,
        method='filter_by_date',
        label=_('Issue Date'),
        help_text=_('When the issue was created')
    )
    date_gte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('From')
    )
    date_lte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('To')
    )

    # Next Action Date filters with helper text
    next_action_date = django_filters.ChoiceFilter(
        choices=CREATION_CHOICES,
        method='filter_by_next_action_date',
        label=_('Next Action Date'),
        help_text=_('When the next action is scheduled')
    )
    next_action_date_gte = django_filters.DateFilter(
        field_name='next_action_date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('From')
    )
    next_action_date_lte = django_filters.DateFilter(
        field_name='next_action_date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('To')
    )
```

**Filter Method:**

```python
def filter_by_next_action_date(self, queryset, name, value):
    today = date.today()
    if value == 'today':
        return queryset.filter(next_action_date=today)
    elif value == 'yesterday':
        return queryset.filter(next_action_date=today - timedelta(1))
    elif value == 'last_7_days':
        return queryset.filter(
            next_action_date__gte=today - timedelta(7),
            next_action_date__lte=today
        )
    elif value == 'next_7_days':
        return queryset.filter(
            next_action_date__gte=today,
            next_action_date__lte=today + timedelta(7)
        )
    elif value == 'last_30_days':
        return queryset.filter(
            next_action_date__gte=today - timedelta(30),
            next_action_date__lte=today
        )
    elif value == 'this_month':
        return queryset.filter(
            next_action_date__month=today.month,
            next_action_date__year=today.year
        )
    elif value == 'last_month':
        month = today.month - 1 if today.month != 1 else 12
        year = today.year if today.month != 1 else today.year - 1
        return queryset.filter(next_action_date__month=month, next_action_date__year=year)
    else:
        return queryset
```

**Filter Options:**

- **Today:** Issues scheduled for today
- **Yesterday:** Overdue issues from yesterday
- **Last 7 days:** Recently scheduled or overdue issues
- **Next 7 days:** ⭐ NEW - Upcoming work in the next week
- **Last 30 days:** Issues scheduled in the past month
- **This month:** All issues scheduled this month
- **Last month:** Issues from previous month
- **Custom:** Specify exact date range with From/To fields

### 3. Added "Next 7 Days" Option

**File:** `support/filters.py`

**Problem:**
The most common use case - finding work scheduled for the next week - wasn't available as a quick filter option.

**Solution:**
Added "Next 7 Days" to `CREATION_CHOICES`:

```python
CREATION_CHOICES = (
    ('today', _('Today')),
    ('yesterday', _('Yesterday')),
    ('last_7_days', _('Last 7 days')),
    ('next_7_days', _('Next 7 days')),  # NEW
    ('last_30_days', _('Last 30 days')),
    ('this_month', _('This month')),
    ('last_month', _('Last month')),
    ('custom', _('Custom')),
)
```

**Benefits:**

- **Quick Access:** One-click filter for upcoming week's work
- **Planning:** Easy to see workload for next 7 days
- **Prioritization:** Helps users focus on near-term tasks
- **Available for Both:** Works for both issue date and next action date

### 4. Helper Text for Date Fields

**File:** `support/filters.py`

**Problem:**
Users were confused about the difference between "Date" and "Next Action Date" fields.

**Solution:**
Added clear helper text to both date filter fields:

- **Issue Date:** "When the issue was created"
- **Next Action Date:** "When the next action is scheduled"

**Template Display:**

```html
<label for="date">
  {{ filter.form.date.label }}
  <small class="text-muted">{{ filter.form.date.help_text }}</small>
</label>
```

**Benefits:**

- **Clear Purpose:** Users understand what each date field represents
- **Reduced Confusion:** No more mixing up creation date vs. action date
- **Better UX:** Contextual help right where it's needed

### 5. Improved Filter Layout

**File:** `support/templates/list_issues.html`

**Problem:**
Date filters were scattered across the form, making it hard to use them together efficiently.

**Solution:**
Organized date fields in a dedicated row with both filters side-by-side:

```html
<div class="row">
  <div class="form-group col-md-6">
    <label for="date">
      {{ filter.form.date.label }}
      <small class="text-muted">{{ filter.form.date.help_text }}</small>
    </label>
    {% render_field filter.form.date class="form-control" %}
  </div>
  <div class="form-group col-md-6">
    <label for="next_action_date">
      {{ filter.form.next_action_date.label }}
      <small class="text-muted">{{ filter.form.next_action_date.help_text }}</small>
    </label>
    {% render_field filter.form.next_action_date class="form-control" %}
  </div>
</div>
```

**Custom Date Ranges:**

```html
<div class="row">
  <div class="creation-range hidden d-none col-md-6">
    <div class="row">
      <div class="form-group col">
        <label for="date_gte">{{ filter.form.date_gte.label }}</label>
        {% render_field filter.form.date_gte class="form-control" %}
      </div>
      <div class="form-group col">
        <label for="date_lte">{{ filter.form.date_lte.label }}</label>
        {% render_field filter.form.date_lte class="form-control" %}
      </div>
    </div>
  </div>
  <div class="next-action-range hidden d-none col-md-6">
    <div class="row">
      <div class="form-group col">
        <label for="next_action_date_gte">{{ filter.form.next_action_date_gte.label }}</label>
        {% render_field filter.form.next_action_date_gte class="form-control" %}
      </div>
      <div class="form-group col">
        <label for="next_action_date_lte">{{ filter.form.next_action_date_lte.label }}</label>
        {% render_field filter.form.next_action_date_lte class="form-control" %}
      </div>
    </div>
  </div>
</div>
```

**Benefits:**

- **Side-by-Side:** Both date filters visible at once
- **Logical Grouping:** Related filters together
- **Efficient Use of Space:** Better screen real estate utilization
- **Parallel Workflow:** Filter by both dates simultaneously

### 6. JavaScript for Next Action Date Range

**File:** `support/templates/list_issues.html`

**Problem:**
Custom date range functionality only worked for issue date, not next action date.

**Solution:**
Added JavaScript to handle custom date range display for next action date:

```javascript
// Date range functionality for Next Action Date
$('#id_next_action_date').change(function(){
  var option = $(this).val();
  if(option == "custom") {
    $('.next-action-range').removeClass('d-none');
  }else {
    $('.next-action-range').addClass('d-none');
    $('#id_next_action_date_gte').attr('value', '');
    $('#id_next_action_date_lte').attr('value', '');
  }
});
$('#id_next_action_date').change();
$('#id_next_action_date_gte').datepicker({ dateFormat: 'yy-mm-dd' });
$('#id_next_action_date_lte').datepicker({ dateFormat: 'yy-mm-dd' });
```

**Features:**

- **Show/Hide Logic:** Custom range fields appear only when "Custom" selected
- **Auto-Clear:** Clears custom dates when switching to preset options
- **Datepicker:** Calendar widget for easy date selection
- **Consistent UX:** Same behavior as issue date filtering

### 7. Sortable Table Columns

**File:** `support/views/all_views.py`

**Problem:**
Users couldn't sort the issue list by date or next_action_date, making it hard to prioritize work.

**Solution:**
Enhanced `IssueListView.get_queryset()` with ordering support:

```python
def get_queryset(self):
    """Get queryset with optional ordering by date or next_action_date"""
    queryset = Issue.objects.all()

    # Get ordering parameter from request
    order_by = self.request.GET.get('order_by', '-date')

    # Validate ordering parameter to prevent SQL injection
    valid_orderings = [
        'date', '-date',
        'next_action_date', '-next_action_date',
        'status', '-status',
        'category', '-category'
    ]

    if order_by in valid_orderings:
        queryset = queryset.order_by(order_by)
    else:
        # Default ordering
        if logistics_is_installed():
            queryset = queryset.order_by(
                "-date", "subscription_product__product",
                "-subscription_product__route__number", "-id"
            )
        else:
            queryset = queryset.order_by("-date", "subscription_product__product", "-id")

    return queryset
```

**Template Implementation:**

```html
<th>
  <a href="?{% for key, value in request.GET.items %}{% if key != 'order_by' and key != 'p' %}{{ key }}={{ value }}&{% endif %}{% endfor %}order_by={% if request.GET.order_by == 'date' %}-date{% else %}date{% endif %}" class="text-dark">
    {% trans "Start date" %}
    {% if request.GET.order_by == 'date' %}<i class="fas fa-sort-up"></i>{% elif request.GET.order_by == '-date' %}<i class="fas fa-sort-down"></i>{% else %}<i class="fas fa-sort"></i>{% endif %}
  </a>
</th>
<th>
  <a href="?{% for key, value in request.GET.items %}{% if key != 'order_by' and key != 'p' %}{{ key }}={{ value }}&{% endif %}{% endfor %}order_by={% if request.GET.order_by == 'next_action_date' %}-next_action_date{% else %}next_action_date{% endif %}" class="text-dark">
    {% trans "Next action date" %}
    {% if request.GET.order_by == 'next_action_date' %}<i class="fas fa-sort-up"></i>{% elif request.GET.order_by == '-next_action_date' %}<i class="fas fa-sort-down"></i>{% else %}<i class="fas fa-sort"></i>{% endif %}
  </a>
</th>
```

**Features:**

- **Clickable Headers:** Click column header to sort
- **Toggle Direction:** Click again to reverse sort order
- **Visual Indicators:** Icons show current sort state
  - <i class="fas fa-sort"></i> - Not sorted by this column
  - <i class="fas fa-sort-up"></i> - Sorted ascending
  - <i class="fas fa-sort-down"></i> - Sorted descending
- **Preserve Filters:** Sorting maintains all active filters
- **Security:** Whitelist validation prevents SQL injection
- **Multiple Columns:** Sort by date, next_action_date, status, or category

**Sort Options:**

- **Start Date:** Sort by issue creation date (ascending/descending)
- **Next Action Date:** Sort by scheduled action date (ascending/descending)
- **Status:** Sort by issue status
- **Category:** Sort by issue category

## Technical Details

### Files Modified

1. **support/views/all_views.py**
   - Added `form_valid()` method to `IssueDetailView` for automatic next_action_date setting
   - Enhanced `get_queryset()` in `IssueListView` with ordering support
   - Added security validation for order_by parameter

2. **support/filters.py**
   - Added "Next 7 days" to `CREATION_CHOICES`
   - Added next_action_date filter fields with helper text
   - Added `filter_by_next_action_date()` method
   - Added helper text to issue date filter
   - Fixed line length linting errors

3. **support/templates/list_issues.html**
   - Reorganized date filters into dedicated row (col-md-6 each)
   - Added helper text display for both date fields
   - Added JavaScript for next action date custom range functionality
   - Added sortable column headers with icons
   - Improved responsive layout

4. **support/models.py**
   - Added help_text to `date` field: "Date of the issue"

### Database Impact

- **No migrations required** - All fields already exist
- **Automatic updates** - next_action_date updated via save() method
- **No data migration needed** - Works with existing data

### Performance Considerations

- **Efficient Updates:** Uses `update_fields=['next_action_date']` to minimize database writes
- **Indexed Fields:** Both date and next_action_date are indexed for fast filtering
- **Query Optimization:** Ordering uses database indexes
- **No N+1 Queries:** All filtering done at database level

## User Experience Improvements

### Before

- **Manual Date Management:** Users had to remember to set next_action_date
- **Limited Filtering:** Could only filter by issue creation date
- **No Quick Filters:** No "next 7 days" option for common use case
- **Unclear Fields:** Confusion between date types
- **No Sorting:** Couldn't prioritize by date
- **Scattered Layout:** Date filters not organized together

### After

- **Automatic Scheduling:** Status changes automatically set next_action_date to tomorrow
- **Comprehensive Filtering:** Filter by both issue date and next action date
- **Quick Access:** "Next 7 days" option for finding upcoming work
- **Clear Labels:** Helper text explains each date field
- **Sortable Columns:** Click headers to sort by any date field
- **Organized Layout:** Both date filters side-by-side with helper text

## Workflow Examples

### Example 1: Daily Work Planning

**User Goal:** Find all issues due today

**Steps:**

1. Go to issue list
2. Select "Today" from Next Action Date dropdown
3. Click Search
4. See all issues scheduled for today

**Result:** Focused list of today's work

### Example 2: Weekly Planning

**User Goal:** See all work scheduled for next week

**Steps:**

1. Go to issue list
2. Select "Next 7 days" from Next Action Date dropdown
3. Click "Next action date" header to sort by date
4. See chronologically ordered list of upcoming work

**Result:** Clear view of next week's workload

### Example 3: Finding Overdue Issues

**User Goal:** Find issues that should have been addressed

**Steps:**

1. Go to issue list
2. Select "Last 7 days" from Next Action Date dropdown
3. Click Search
4. See issues with past next action dates

**Result:** List of overdue follow-ups that need attention

### Example 4: Status Change Workflow

**User Goal:** Update issue status and ensure follow-up

**Steps:**

1. Open issue detail page
2. Change status from "Open" to "In Progress"
3. Save issue
4. System automatically sets next_action_date to tomorrow

**Result:** Issue has scheduled follow-up without manual date entry

## Benefits

1. **Improved Workflow Efficiency:**
   - Automatic next_action_date setting saves time
   - Quick filters reduce clicks to find relevant issues
   - Sorting helps prioritize work

2. **Better Data Quality:**
   - Ensures all status changes have follow-up dates
   - Reduces forgotten follow-ups
   - Maintains consistent scheduling

3. **Enhanced User Experience:**
   - Clear helper text reduces confusion
   - Organized layout improves usability
   - Visual sort indicators provide feedback

4. **Powerful Filtering:**
   - Find issues by creation date or action date
   - Multiple preset options for common use cases
   - Custom date ranges for specific needs

5. **Increased Productivity:**
   - "Next 7 days" filter for weekly planning
   - Sortable columns for prioritization
   - Side-by-side filters for complex queries

## Migration Notes

- **No database migration required** - All fields already exist in Issue model
- **Immediate effect** - Automatic date setting works as soon as deployed
- **Backward compatible** - Existing issues and workflows unaffected
- **No training required** - Intuitive UI with helper text

## Testing Recommendations

### Manual Testing

1. **Test automatic next_action_date setting:**
   - Create issue with status "Open"
   - Change status to "In Progress"
   - Verify next_action_date is set to tomorrow
   - Change status again with future next_action_date
   - Verify future date is preserved

2. **Test next action date filtering:**
   - Filter by "Today"
   - Filter by "Next 7 days"
   - Filter by "Last 7 days"
   - Test custom date range
   - Verify results are correct

3. **Test sorting:**
   - Sort by Start date (ascending/descending)
   - Sort by Next action date (ascending/descending)
   - Verify sort icons update correctly
   - Verify filters are preserved when sorting

4. **Test filter layout:**
   - Verify both date filters visible side-by-side
   - Verify helper text displays correctly
   - Test custom range show/hide for both dates
   - Test responsive layout on mobile

### Edge Cases

1. **Null next_action_date:** Verify automatic setting works
2. **Past next_action_date:** Verify it gets updated to tomorrow
3. **Future next_action_date:** Verify it's not changed
4. **No status change:** Verify next_action_date not modified
5. **Empty filter results:** Verify appropriate message

## Future Considerations

1. **Configurable Default:** Allow setting default next_action_date offset (e.g., 2 days, 1 week)
2. **Status-Specific Dates:** Different default dates for different status changes
3. **Bulk Actions:** Update next_action_date for multiple issues at once
4. **Calendar View:** Visual calendar showing issues by next_action_date
5. **Reminders:** Email notifications for upcoming next_action_dates
6. **Smart Suggestions:** ML-based next_action_date recommendations

## Related Components

- **Issue Model:** `support/models.py` - Defines issue data structure
- **Issue Forms:** `support/forms.py` - Issue creation and editing forms
- **Issue Detail View:** `support/views/all_views.py` - Individual issue management
- **Issue List View:** `support/views/all_views.py` - Issue browsing and filtering

## Conclusion

This comprehensive enhancement significantly improves the issue management workflow by automating next_action_date setting, providing powerful filtering capabilities, and improving the user interface. The automatic date setting ensures no follow-ups are forgotten, while the enhanced filtering and sorting make it easy to find and prioritize work. The addition of helper text and improved layout creates a more intuitive user experience, and the "Next 7 days" filter addresses a common use case for weekly planning. These changes combine to create a more efficient and user-friendly issue management system.
