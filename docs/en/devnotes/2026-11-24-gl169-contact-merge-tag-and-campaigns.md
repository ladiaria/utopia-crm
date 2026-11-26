# Contact merge: the merged-away tag stays on the source, and worked campaigns move

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#169
- **Type:** Bug Fix
- **Component:** core (Contact merge)
- **Impact:** Call center, campaigns

## 🎯 Summary

`Contact.merge_other_contact_into_this` does not delete the contact merged away: it moves its data to the contact that stays and tags the source `eliminar`. Two things went wrong there. It copied every tag of the source, so a source that had already been merged away passed the `eliminar` mark to the contact that stays. And its `ContactCampaignStatus` rows were either all deleted, history included, when the contact that stays was in any campaign, or all left on the empty source, still assigned to a seller, when it was not. At la diaria, campaigns of merged-away contacts are loaded by hand into a high-priority campaign, and 46 contacts with an active subscription ended up there, hidden from every other campaign in the seller console. The merge now keeps the mark on the source, moves the campaigns that were already worked to the contact that stays and deletes the open ones.

## ✨ Changes

### 1. The `eliminar` tag is not copied

**File:** `core/models.py`

The tag name becomes the module constant `MERGED_AWAY_CONTACT_TAG`, and the loop that copies the tags of the source skips it:

```python
for tag in source.tags.exclude(name=MERGED_AWAY_CONTACT_TAG):
    self.tags.add(tag.name)
```

The source still gets the tag at the end of the merge.

### 2. What happens to the campaigns of the source

**Files:** `core/models.py`, `core/choices.py`

```python
source_statuses = source.contactcampaignstatus_set
source_statuses.filter(status__in=OPEN_CAMPAIGN_STATUSES).delete()
source_statuses.filter(campaign__in=self.contactcampaignstatus_set.values("campaign")).delete()
source_statuses.update(contact=self)
```

- **Open statuses are deleted:** «Not yet contacted», «Called, could not contact», «Switch to morning» and «Switch to afternoon/evening», the new list `OPEN_CAMPAIGN_STATUSES` in `core/choices.py`. The merge already deleted the pending activities of the source that have a campaign; this is the same rule for its campaign status.
- **Where both contacts are in the same campaign**, the status of the contact that stays wins: `ContactCampaignStatus` is unique on `(contact, campaign)`.
- **The rest move to the contact that stays** (Contacted, Ended with contact, Ended without contact), with their seller, resolution and dates, so the campaign history of the person is kept.

## 📁 Modified Files

- **`core/models.py`** — `MERGED_AWAY_CONTACT_TAG`; `merge_other_contact_into_this` skips that tag when copying and handles the campaigns of the source as above
- **`core/choices.py`** — `OPEN_CAMPAIGN_STATUSES`
- **`CHANGELOG.md`** — Entry for this change

## 📁 Created Files

- **`tests/test_contact_merge.py`** — The `eliminar` tag is not copied and the source gets it; worked campaigns move, also when the contact that stays is in another campaign; open ones are deleted, also when the contact that stays is in none; where both are in a campaign, the status of the contact that stays wins. With the previous code, three of the five tests fail

## 🧪 Manual Testing

1. **Normal case:** take two contacts. Give the source a tag, a campaign ended with contact and a campaign in «Not yet contacted» with a seller. Merge it into the other one from the merge screen. **Check:** the contact that stays has the tag and the ended campaign, not the open one; the source has no campaigns left and has the `eliminar` tag.
2. **Edge case, a source already merged away:** tag the source `eliminar` by hand before merging. **Check:** the contact that stays does not get `eliminar`.
3. **Edge case, same campaign:** put both contacts in one campaign, the one that stays in «Not yet contacted» and the source ended. **Check:** after merging, the contact that stays keeps «Not yet contacted» in that campaign.

## 📝 Deployment Notes

- No migrations, no settings.
- Merges already done do not change. Contacts that already got the `eliminar` tag, or that sit in a campaign of merged-away contacts, are handled in it/utopia-crm-ladiaria#169.

## 🎓 Design Decisions

- **Open campaigns are deleted, not moved.** Moving them would put the contact that stays in every campaign the source was waiting in. If one of them is the high-priority campaign of merged-away contacts, the contact that stays would be reserved there and hidden from every other campaign (`Campaign.get_not_contacted`), which is how the 46 contacts got hidden.
- **The status of the contact that stays wins** on a shared campaign, as before: it is the contact the call center keeps working.

---

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl169-fusion-etiqueta-y-campanias
- **Type:** Bug Fix
- **Modules affected:** core
