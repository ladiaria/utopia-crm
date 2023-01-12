from django.db.models import Manager


class ProductManager(Manager):

    def get_by_natural_key(self, slug):
        return self.get(slug=slug)
