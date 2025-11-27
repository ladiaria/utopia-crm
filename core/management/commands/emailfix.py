# coding=utf-8
from csv import writer

from django.db import connection
from django.db.utils import IntegrityError
from django.core.management import BaseCommand, CommandError

from core.models import EmailReplacement


class Command(BaseCommand):
    help = "Applies the actual approved email fix replacements to all contacts"

    def add_arguments(self, parser):
        parser.add_argument(
            '--export-replacements',
            type=str,
            action='store',
            dest='export_replacements',
            help='Additionaly exports the approved replacements entries to this CSV file path',
        )
        parser.add_argument(
            '--print-sql',
            action='store_true',
            default=False,
            dest='print_sql',
            help='Print the SQL statements that will be executed',
        )

    def handle(self, *args, **options):
        replacements, export_replacements = EmailReplacement.approved().items(), options.get("export_replacements")
        print_sql = options.get("print_sql")
        with connection.cursor() as cursor:
            for domain, replacement in replacements:
                domain_dot_escaped = domain.replace('.', '\.')
                try:
                    update_query = (
                        """
                        UPDATE core_contact SET email=REGEXP_REPLACE(email,'@%s','@%s','i')
                        WHERE email ~* '@%s$'
                        """ % (domain_dot_escaped, replacement, domain_dot_escaped)
                    )
                    if print_sql:
                        print(update_query)
                    cursor.execute(update_query)
                except IntegrityError as ieexc:
                    print(f"\nReplacement failed: {domain} -> {replacement}")
                    print(ieexc)
        if export_replacements:
            try:
                writer(open(export_replacements, "w")).writerows(replacements)
            except FileNotFoundError as fnfeexc:
                raise CommandError(fnfeexc, returncode=0)
