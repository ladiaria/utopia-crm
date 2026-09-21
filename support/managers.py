from django.db.models import Manager


class IssueSubcategoryManager(Manager):

    def get_by_natural_key(self, name, slug):
        return self.get(name=name, slug=slug)
