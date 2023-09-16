# coding=utf-8
from csv import writer

from django.db import connection
from django.db.utils import IntegrityError
from django.core.management import BaseCommand, CommandError

from core.models import EmailReplacement


class Command(BaseCommand):
    """
    Applies the actual approved email fix replacements to all contacts.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--export-replacements',
            action='store',
            dest='export_replacements',
            help='Additionaly exports the approved replacements entries to this CSV file path',
        )

    def handle(self, *args, **options):
        replacements, export_replacements = EmailReplacement.approved().items(), options.get("export_replacements")
        with connection.cursor() as cursor:
            for domain, replacement in replacements:
                domain_dot_escaped = domain.replace('.', '\.')
                try:
                    cursor.execute(
                        """
                        UPDATE core_contact SET email=REGEXP_REPLACE(email,'@%s','@%s','i')
                        WHERE email ~* '@%s$'
                        """ % (domain_dot_escaped, replacement, domain_dot_escaped)
                    )
                except IntegrityError as ieexc:
                    print(ieexc)
        if export_replacements:
            try:
                writer(open(export_replacements, "w")).writerows(replacements)
            except FileNotFoundError as fnfeexc:
                raise CommandError(fnfeexc, returncode=0)
