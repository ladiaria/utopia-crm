# coding=utf-8
"""
Contact.merge_other_contact_into_this: what happens to the tags and the campaigns of the contact merged away.

The merged-away contact is not deleted: it gets the "eliminar" tag. Copying every tag of the source to the contact that
stays also copied that mark when the source had been merged away before, so a contact with active subscriptions could
end up marked for deletion. The campaigns of the source were all deleted when the contact that stays was in some campaign,
history included, and otherwise they stayed on the empty source, assigned to a seller (it/utopia-crm-ladiaria#169).
"""
from django.test import TestCase

from core.choices import CAMPAIGN_STATUS
from core.models import MERGED_AWAY_CONTACT_TAG, ContactCampaignStatus

from tests.factory import create_campaign, create_contact


class TestContactMerge(TestCase):
    def setUp(self):
        self.target = create_contact(name="Stays", phone="099111222")
        self.source = create_contact(name="Merged away", phone="099333444")

    def merge(self):
        errors = self.target.merge_other_contact_into_this(self.source)
        self.assertEqual(errors, [])

    def status(self, contact, campaign, status):
        return ContactCampaignStatus.objects.create(contact=contact, campaign=campaign, status=status)

    def test_the_merged_away_tag_is_not_copied(self):
        self.source.tags.add(MERGED_AWAY_CONTACT_TAG, "promo_2024")

        self.merge()

        self.assertEqual(sorted(self.target.tags.names()), ["promo_2024"])
        self.assertIn(MERGED_AWAY_CONTACT_TAG, self.source.tags.names())

    def test_the_source_is_marked_for_deletion(self):
        self.merge()

        self.assertIn(MERGED_AWAY_CONTACT_TAG, self.source.tags.names())
        self.assertNotIn(MERGED_AWAY_CONTACT_TAG, self.target.tags.names())

    def test_worked_campaigns_move_to_the_contact_that_stays(self):
        self.status(self.target, create_campaign("Target's campaign"), CAMPAIGN_STATUS.NOT_YET_CONTACTED)
        worked = {
            create_campaign("Contacted"): CAMPAIGN_STATUS.CONTACTED,
            create_campaign("Ended with contact"): CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
            create_campaign("Ended without contact"): CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
        }
        ids = [self.status(self.source, campaign, status).pk for campaign, status in worked.items()]

        self.merge()

        self.assertFalse(self.source.contactcampaignstatus_set.exists())
        moved = ContactCampaignStatus.objects.filter(pk__in=ids)
        self.assertEqual(set(moved.values_list("contact", flat=True)), {self.target.pk})
        self.assertEqual({ccs.campaign: ccs.status for ccs in moved}, worked)

    def test_open_campaigns_are_deleted(self):
        for name, status in (
            ("Not yet contacted", CAMPAIGN_STATUS.NOT_YET_CONTACTED),
            ("Could not contact", CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT),
            ("Switch to morning", CAMPAIGN_STATUS.SWITCH_TO_MORNING),
            ("Switch to afternoon", CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON),
        ):
            self.status(self.source, create_campaign(name), status)

        self.merge()

        self.assertFalse(self.source.contactcampaignstatus_set.exists())
        self.assertFalse(self.target.contactcampaignstatus_set.exists())

    def test_where_both_are_in_the_campaign_the_status_of_the_contact_that_stays_wins(self):
        campaign = create_campaign("Both")
        kept = self.status(self.target, campaign, CAMPAIGN_STATUS.NOT_YET_CONTACTED)
        self.status(self.source, campaign, CAMPAIGN_STATUS.ENDED_WITH_CONTACT)

        self.merge()

        self.assertFalse(self.source.contactcampaignstatus_set.exists())
        self.assertEqual(list(self.target.contactcampaignstatus_set.all()), [kept])
        kept.refresh_from_db()
        self.assertEqual(kept.status, CAMPAIGN_STATUS.NOT_YET_CONTACTED)
