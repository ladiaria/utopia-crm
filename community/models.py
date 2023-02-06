# coding=utf-8


from django.utils.translation import gettext_lazy as _

from django.db import models


class ProductParticipation(models.Model):
    contact = models.ForeignKey('core.contact', on_delete=models.CASCADE)
    product = models.ForeignKey('core.product', on_delete=models.CASCADE)
    description = models.TextField('Descripción', null=True, blank=True)

    def __str__(self):
        return _('Participation {} by subscriber {}'.format(self.product, self.contact))

    class Meta:
        verbose_name_plural = _('Participations in products or events')


class Support(models.Model):
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'), null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = _('Supports')


class Supporter(models.Model):
    contact = models.ForeignKey('core.contact', on_delete=models.CASCADE)
    support = models.ForeignKey(Support, on_delete=models.CASCADE)
    description = models.TextField('Descripción', null=True, blank=True)

    def __str__(self):
        return '%s apoya en %s' % (
            self.contact, self.support)

    class Meta:
        verbose_name_plural = _('Supporters')
