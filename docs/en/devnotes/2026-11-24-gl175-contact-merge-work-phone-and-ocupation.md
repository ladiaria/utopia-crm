# Contact merge: the chosen work phone and ocupation are kept

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#175
- **Type:** Bug Fix
- **Component:** core (Contact merge)
- **Impact:** Anyone who merges duplicated contacts

## 🎯 Summary

`Contact.merge_other_contact_into_this` takes the data chosen on the merge screen as keyword arguments and writes them on the contact that stays. Two of them were written wrong. The work phone was assigned the value of `phone`, so the contact that stays got its regular phone as work phone, and when no phone was chosen the merge raised `AttributeError` halfway through. The ocupation id was converted with `int()`, but `Ocupation`'s primary key is a three-character code such as `"011"`: the leading zero was lost and the contact pointed to an ocupation that does not exist. Both now keep the value as chosen. The method also set a misspelled `not_email` attribute instead of `no_email`; it was harmless, because `Contact.save()` recalculates `no_email`, but it is fixed too.

These fixes came up while making la diaria's merge screen safer (it/utopia-crm-ladiaria#175), which now offers the work phone, last name and ocupation that its previous version did not send.

## ✨ Changes

### 1. Work phone

**File:** `core/models.py`

```python
if work_phone:
    self.work_phone = work_phone.strip()
```

### 2. Ocupation

**File:** `core/models.py`

```python
if ocupation_id:
    # Ocupation's primary key is a code like "011": as an int it would lose the leading zero.
    self.ocupation_id = ocupation_id.strip()
```

### 3. `no_email`

**File:** `core/models.py`

When the chosen email is empty the contact that stays gets `no_email = True`, and `False` otherwise, instead of setting an attribute that does not exist on the model.

## 📁 Modified Files

- **`core/models.py`** — `merge_other_contact_into_this` writes `work_phone` and `ocupation_id` as chosen, and `no_email` with its real name
- **`tests/test_contact_merge.py`** — New `TestContactMergeOverrides`: the chosen work phone is kept, also without a phone, and an ocupation code with a leading zero is kept. With the previous code the three tests fail
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

1. **Normal case:** take two contacts with different phones, one of them with a work phone. Merge them choosing that work phone. **Check:** the contact that stays has that work phone, not its regular phone.
2. **Edge case, no phone:** neither contact has a regular phone, one has a work phone. Merge choosing it. **Check:** the merge finishes without errors and the contact that stays has the work phone.
3. **Edge case, ocupation with a leading zero:** give one contact the ocupation «011» and merge choosing it. **Check:** the contact that stays shows that ocupation.

## 📝 Deployment Notes

- No migrations, no settings.
- Deploy it before, or together with, the merge screen of it/utopia-crm-ladiaria#175: that screen sends the ocupation, and without this fix a code with a leading zero makes the merge fail.

---

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl175-merge-work-phone
- **Type:** Bug Fix
- **Modules affected:** core
