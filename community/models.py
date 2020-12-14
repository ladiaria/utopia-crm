# coding=utf-8
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from django.db import models


class ProductParticipation(models.Model):
    contact = models.ForeignKey('core.contact')
    product = models.ForeignKey('core.product')
    description = models.TextField(u'Descripción', null=True, blank=True)

    def __unicode__(self):
        return _('Participation {} by subscriber {}'.format(self.product, self.contact))

    class Meta:
        verbose_name_plural = _('Participations in products or events')


class Support(models.Model):
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'), null=True, blank=True)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name_plural = _('Supports')


class Supporter(models.Model):
    contact = models.ForeignKey('core.contact')
    support = models.ForeignKey(Support)
    description = models.TextField(u'Descripción', null=True, blank=True)

    def __unicode__(self):
        return '%s apoya en %s' % (
            self.contact, self.support)

    class Meta:
        verbose_name_plural = _('Supporters')
