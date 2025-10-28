import io
import pandas as pd

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from faker import Faker

from core.models import Address, Contact, IdDocumentType
from tests.factories import ContactFactory, SubscriptionFactory, CampaignFactory


class ImportContactsViewTest(TestCase):
    def setUp(self):
        self.url = reverse('import_contacts')
        self.client = self.client_class()
        self.user = User.objects.create_user(username='testuser', password='testpassword', is_staff=True)
        self.client.login(username='testuser', password='testpassword')
        
        # Create common ID document types for tests (must provide explicit IDs)
        self.doc_type_ci, _ = IdDocumentType.objects.get_or_create(
            id=1, defaults={'name': 'CI'}
        )
        self.doc_type_cc, _ = IdDocumentType.objects.get_or_create(
            id=2, defaults={'name': 'CC'}
        )

    def create_csv_file(self, data):
        csv_data = pd.DataFrame(data)
        csv_buffer = io.StringIO()
        csv_data.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return SimpleUploadedFile("test.csv", csv_buffer.getvalue().encode('utf-8'), content_type="text/csv")

    def test_import_new_contact(self):
        csv_file = self.create_csv_file(
            [
                {
                    'name': 'John',
                    'last_name': 'Doe',
                    'email': 'john@gmail.com',
                    'phone': '59892301380',
                    'mobile': '',
                    'notes': 'Test notes',
                    'address_1': '123 Test St',
                    'address_2': 'Apt 4',
                    'city': 'Test City',
                    'state': '',
                    'country': 'Test Country',
                    'id_document_type': '',
                    'id_document': '123456',
                    'ranking': '5',
                }
            ]
        )

        form_data = {
            'file': csv_file,
            'use_headers': True,
            'tags': 'new,test',
            'tags_existing': 'existing',
            'tags_active': 'active_subscription',
            'tags_in_campaign': 'in_campaign',
        }

        response = self.client.post(self.url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Check if contact was created
        self.assertTrue(Contact.objects.filter(email='john@gmail.com').exists())
        self.assertTrue(Contact.objects.all().count() == 1)
        contact = Contact.objects.get(email='john@gmail.com')

        # Check if address was created
        self.assertTrue(Address.objects.filter(contact=contact).exists())

        # Check if the tags were added
        self.assertIn('new', contact.tags.names())
        self.assertIn('test', contact.tags.names())

        # Check if tags_existing, tags_active and tags_in_campaign were not added
        self.assertNotIn('existing', contact.tags.names())
        self.assertNotIn('active_subscription', contact.tags.names())
        self.assertNotIn('in_campaign', contact.tags.names())

    def test_update_phone_of_existing_contact(self):
        # Create an existing contact, we need to override the phone and mobile with empty strings because
        # the factory creates random phone numbers by default
        contact = ContactFactory.create(name='Jane', email='jane@gmail.com', phone="", mobile="")

        new_phone = Faker().phone_number()

        csv_file = self.create_csv_file(
            [
                {
                    'name': 'Jane',
                    'last_name': 'Doe',
                    'email': 'jane@gmail.com',
                    'phone': new_phone,
                    'mobile': "",
                    'notes': 'Updated notes',
                    'address_1': '456 Test Ave',
                    'address_2': '',
                    'city': 'Another City',
                    'state': 'AC',
                    'country': 'Another Country',
                    'id_document_type': '',
                    'id_document': 'DL987654',
                    'ranking': '4',
                }
            ]
        )

        form_data = {
            'file': csv_file,
            'use_headers': True,
            'tags': 'added_new_phone',  # Tags are always required
            'tags_existing': 'existing,updated',
        }

        response = self.client.post(self.url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Check if contact was updated
        contact.refresh_from_db()
        self.assertEqual(contact.phone, new_phone)

        # Check if tags were added
        self.assertIn('existing', contact.tags.names())
        self.assertIn('updated', contact.tags.names())

        # Check if an address was not created as this is not a new contact
        self.assertFalse(Address.objects.filter(contact=contact).exists())

    def test_update_email_of_existing_contact(self):
        # Create an existing contact, the phones will be created by the factory
        contact1 = ContactFactory.create(name='Contact 1', email='')
        contact2 = ContactFactory.create(name='Contact 2', email='contact2@gmail.com')

        # The factory already creates a phone for each contact, we're going to create a csv with their phone numbers
        csv_file = self.create_csv_file(
            [
                {
                    'name': 'Contact 1',
                    'last_name': '',
                    'email': 'newemail@gmail.com',
                    'phone': contact1.phone,
                    'mobile': '',
                    'notes': '',
                    'address_1': '',
                    'address_2': '',
                    'city': '',
                    'state': '',
                    'country': '',
                    'id_document_type': '',
                    'id_document': '',
                    'ranking': '',
                },
                {
                    'name': 'Contact 2',
                    'last_name': '',
                    'email': 'newemail2@gmail.com',
                    'phone': contact2.phone,
                    'mobile': '',
                    'notes': '',
                    'address_1': '',
                    'address_2': '',
                    'city': '',
                    'state': '',
                    'country': '',
                    'id_document_type': '',
                    'id_document': '',
                    'ranking': '',
                },
            ]
        )

        form_data = {
            'file': csv_file,
            'use_headers': True,
            'tags': 'updated_email',  # Tags are always required
        }

        response = self.client.post(self.url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # First we need to check if contact 1 was updated
        contact1.refresh_from_db()
        self.assertEqual(contact1.email, 'newemail@gmail.com')

        # Then we need to check if contact 2 was NOT updated because it already has an email
        contact2.refresh_from_db()
        self.assertEqual(contact2.email, 'contact2@gmail.com')

    def test_import_contact_that_already_has_an_active_subscription(self):
        contact = ContactFactory.create(name='Contact with subscription', email='contact_with_subscription@gmail.com')
        SubscriptionFactory.create(contact=contact, active=True, type="N")

        csv_file = self.create_csv_file(
            [
                {
                    'name': 'Contact with subscription',
                    'last_name': '',
                    'email': 'contact_with_subscription@gmail.com',
                    'phone': '',
                    'mobile': '',
                    'notes': '',
                    'address_1': '',
                    'address_2': '',
                    'city': '',
                    'state': '',
                    'country': '',
                    'id_document_type': '',
                    'id_document': '',
                    'ranking': '',
                }
            ]
        )

        form_data = {
            'file': csv_file,
            'use_headers': True,
            'tags': 'new_subscription',
            'tags_active': 'active_subscription',
        }

        response = self.client.post(self.url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Check that there is only one contact
        self.assertEqual(Contact.objects.all().count(), 1)

        # Check if tags were added
        self.assertIn('active_subscription', contact.tags.names())

    def test_import_contact_that_is_already_in_campaign(self):
        contact = ContactFactory.create(name='Contact in campaign', email='contact_in_campaign@gmail.com')
        campaign = CampaignFactory.create()
        contact.add_to_campaign(campaign.id)

        csv_file = self.create_csv_file(
            [
                {
                    'name': 'Contact in campaign',
                    'last_name': '',
                    'email': 'contact_in_campaign@gmail.com',
                    'phone': '',
                    'mobile': '',
                    'notes': '',
                    'address_1': '',
                    'address_2': '',
                    'city': '',
                    'state': '',
                    'country': '',
                    'id_document_type': '',
                    'id_document': '',
                    'ranking': '',
                }
            ]
        )

        form_data = {
            'file': csv_file,
            'use_headers': True,
            'tags': 'new, other',
            'tags_existing': 'existing',
            'tags_in_campaign': 'in_campaign',
        }

        response = self.client.post(self.url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirect on success

        # Check that there is only one contact
        self.assertEqual(Contact.objects.all().count(), 1)

        contact.refresh_from_db()

        # Check if tags were added
        self.assertIn('in_campaign', contact.tags.names())

    def test_import_without_headers(self):
        """Test importing CSV file without headers using use_headers=False"""
        # Create CSV data without headers (raw data only)
        # Expected columns (13 total):
        # name, last_name, email, phone, mobile, notes,
        # address_1, address_2, city, state, country,
        # id_document_type, id_document
        csv_content = (
            "Juan,Perez,juan@example.com,24000000,092123456,Test notes,Calle 123,Apt 1,"
            "Montevideo,Montevideo,Uruguay,,12345678\n"
        )

        csv_file = SimpleUploadedFile(
            "test_no_headers.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        form_data = {
            'file': csv_file,
            'use_headers': False,  # No headers in CSV
            'tags': 'no_headers_test',
        }

        response = self.client.post(self.url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirect on success
        # Check if contact was created
        self.assertTrue(Contact.objects.filter(email='juan@example.com').exists())
        contact = Contact.objects.get(email='juan@example.com')

        # Verify contact data
        self.assertEqual(contact.name, 'Juan')
        self.assertEqual(contact.last_name, 'Perez')
        self.assertEqual(contact.phone, '24000000')
        self.assertEqual(contact.mobile, '092123456')

        # Check if tags were added
        self.assertIn('no_headers_test', contact.tags.names())

    def test_download_template(self):
        """Test downloading the CSV template"""
        response = self.client.get(self.url, {'download_template': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="import_contacts_template.csv"'
        )

        # Check that the response contains the expected headers
        content = response.content.decode('utf-8')
        self.assertIn('name,last_name,email,phone,mobile,notes', content)
        self.assertIn('address_1,address_2,city,state,country', content)
        self.assertIn('id_document_type,id_document', content)

        # Check that example data is present
        self.assertIn('Juan', content)
        self.assertIn('Perez', content)
        self.assertIn('juan.perez@example.com', content)

    def test_form_displays_use_headers_field(self):
        """Test that the form displays the use_headers checkbox"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'use_headers')
        self.assertContains(response, 'id_use_headers')
        # Check for download template link (not checking exact text due to i18n)
        self.assertContains(response, '?download_template=1')

    def test_import_with_invalid_document_type(self):
        """Test that invalid document types generate warnings but don't break import"""
        csv_file = self.create_csv_file(
            [
                {
                    'name': 'Maria',
                    'last_name': 'Garcia',
                    'email': 'maria@example.com',
                    'phone': '24111111',
                    'mobile': '092111111',
                    'notes': 'Test with invalid doc type',
                    'address_1': '',
                    'address_2': '',
                    'city': '',
                    'state': '',
                    'country': '',
                    'id_document_type': 'INVALID_TYPE',  # Invalid type
                    'id_document': '99999999',
                }
            ]
        )

        form_data = {
            'file': csv_file,
            'use_headers': True,
            'tags': 'test_invalid_doc',
        }

        response = self.client.post(self.url, form_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Contact should be created despite invalid document type
        self.assertTrue(Contact.objects.filter(email='maria@example.com').exists())
        contact = Contact.objects.get(email='maria@example.com')

        # Document type should be None
        self.assertIsNone(contact.id_document_type)
        
        # Document number should still be saved
        self.assertEqual(contact.id_document, '99999999')

        # Check that a warning message was generated
        messages_list = list(response.context['messages'])
        warning_found = any(
            'Invalid ID document type' in str(msg) and 'INVALID_TYPE' in str(msg)
            for msg in messages_list
        )
        self.assertTrue(warning_found, "Expected warning message about invalid document type")
