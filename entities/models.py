from django.db import models
#from reversion import revisions as reversion
import reversion
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from guardian.shortcuts import assign_perm, remove_perm

from metainfo.models import TempEntityClass, Uri, Text, Collection
from labels.models import Label
from vocabularies.models import (ProfessionType, PlaceType, InstitutionType,
    EventType, Title, WorkType)
from apis.settings.base import BASE_URI
from apis.settings.base import BASE_DIR

import re
import unicodedata


@reversion.register(follow=['tempentityclass_ptr'])
class Person(TempEntityClass):
    """ A temporalized entity to model a human beeing."""

    GENDER_CHOICES = (('female', 'female'), ('male', 'male'))
    first_name = models.CharField(
        max_length=255,
        help_text='The persons´s forename. In case of more then one name...',
        blank=True,
        null=True)
    profession = models.ManyToManyField(ProfessionType, blank=True)
    title = models.ManyToManyField(Title, blank=True)
    gender = models.CharField(
        max_length=15, choices=GENDER_CHOICES,
        blank=True)

    def __str__(self):
        if self.first_name != "" and self.name != "":
            return "{}, {}".format(self.name, self.first_name)
        elif self.first_name != "" and self.name == "":
            return "{}, {}".format("no surename provided", self.first_name)
        elif self.first_name == "" and self.name != "":
            return self.name
        elif self.first_name == "" and self.name == "":
            return "no name provided"

    def get_or_create_uri(uri):
        try:
            if re.match(r'^[0-9]*$', uri):
                p = Person.objects.get(pk=uri)
            else:
                p = Person.objects.get(uri__uri=uri)
            return p
        except:
            return False

    def save(self, *args, **kwargs):
        if self.first_name:
            if self.first_name != unicodedata.normalize('NFC', self.first_name):    #secure correct unicode encoding
                self.first_name = unicodedata.normalize('NFC', self.first_name)
        super(Person, self).save(*args, **kwargs)
        return self


@reversion.register(follow=['tempentityclass_ptr'])
class Place(TempEntityClass):
    """ A temporalized entity to model a place"""

    kind = models.ForeignKey(PlaceType, blank=True, null=True)
    lat = models.FloatField(blank=True, null=True, verbose_name='latitude')
    lng = models.FloatField(blank=True, null=True, verbose_name='longitude')

    def __str__(self):
        if self.name != "":
            return self.name
        else:
            return "no name provided"

    def get_or_create_uri(uri):
        try:
            if re.match(r'^[0-9]*$', uri):
                p = Place.objects.get(pk=uri)
            else:
                p = Place.objects.get(uri__uri=uri)
            return p
        except:
            return False


@reversion.register(follow=['tempentityclass_ptr'])
class Institution(TempEntityClass):
    kind = models.ForeignKey(InstitutionType, blank=True, null=True)
    homepage = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

    def get_or_create_uri(uri):
        try:
            if re.match(r'^[0-9]*$', uri):
                p = Institution.objects.get(pk=uri)
            else:
                p = Institution.objects.get(uri__uri=uri)
                print(p)
            return p
        except:
            print('returned false')
            return False


@reversion.register(follow=['tempentityclass_ptr'])
class Event(TempEntityClass):
    kind = models.ForeignKey(EventType, blank=True, null=True)

    def __str__(self):
        return self.name

    def get_or_create_uri(uri):
        try:
            if re.match(r'^[0-9]*$', uri):
                p = Event.objects.get(pk=uri)
            else:
                p = Event.objects.get(uri__uri=uri)
            return p
        except:
            return False


@reversion.register(follow=['tempentityclass_ptr'])
class Work(TempEntityClass):
    kind = models.ForeignKey(WorkType, blank=True, null=True)

    def __str__(self):
        return self.name

    def get_or_create_uri(uri):
        try:
            if re.match(r'^[0-9]*$', uri):
                p = Work.objects.get(pk=uri)
            else:
                p = Work.objects.get(uri__uri=uri)
            return p
        except:
            return False


@receiver(post_save, sender=Event, dispatch_uid="create_default_uri")
@receiver(post_save, sender=Work, dispatch_uid="create_default_uri")
@receiver(post_save, sender=Institution, dispatch_uid="create_default_uri")
@receiver(post_save, sender=Person, dispatch_uid="create_default_uri")
@receiver(post_save, sender=Place, dispatch_uid="create_default_uri")
def create_default_uri(sender, instance, **kwargs):
    uri = Uri.objects.filter(entity=instance)
    if uri.count() == 0:
        uri2 = Uri(
                uri=''.join((BASE_URI, str(instance.pk))),
                domain='apis default',
                entity=instance)
        uri2.save()


@receiver(m2m_changed, sender=Event.collection.through, dispatch_uid="create_object_permissions")
@receiver(m2m_changed, sender=Work.collection.through, dispatch_uid="create_object_permissions")
@receiver(m2m_changed, sender=Institution.collection.through, dispatch_uid="create_object_permissions")
@receiver(m2m_changed, sender=Person.collection.through, dispatch_uid="create_object_permissions")
@receiver(m2m_changed, sender=Place.collection.through, dispatch_uid="create_object_permissions")
def create_object_permissions(sender, instance, **kwargs):
    if kwargs['action'] == 'pre_add':
        perms = []
        for j in kwargs['model'].objects.filter(pk__in=kwargs['pk_set']):
            perms.extend(j.groups_allowed.all())
        for x in perms:
            assign_perm('change_'+instance.__class__.__name__.lower(), x, instance)
            assign_perm('delete_'+instance.__class__.__name__.lower(), x, instance)
    elif kwargs['action'] == 'post_remove':
        perms = []
        perms_keep = []
        for j in kwargs['model'].objects.filter(pk__in=kwargs['pk_set']):
            perms.extend(j.groups_allowed.all())
        for u in instance.collection.all():
            perms_keep.extend(u.groups_allowed.all())
        rm_perms = set(perms) - set(perms_keep)
        for x in rm_perms:
            remove_perm('change_'+instance.__class__.__name__.lower(), x, instance)
            remove_perm('delete_'+instance.__class__.__name__.lower(), x, instance)


@receiver(m2m_changed, sender=Collection.groups_allowed.through, dispatch_uid="add_usergroup_collection")
def add_usergroup_collection(sender, instance, **kwargs):
    if kwargs['action'] == 'pre_add':
        for x in kwargs['model'].objects.filter(pk__in=kwargs['pk_set']):
            for z in ['change', 'delete']:
                for y in [Person, Institution, Place, Event, Work]:
                    assign_perm(
                        z+'_'+y.__name__.lower(),
                        x,
                        y.objects.filter(collection=instance))
