import datetime
import os
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import get_model
from django.db.models.fields.related import ReverseSingleRelatedObjectDescriptor
from django.conf import settings
from django.db.models.loading import load_app
from django.core.management import call_command
from eventtools.tests.eventtools_testapp.models import *
from datetime import date, datetime, time

class TestModelMetaClass(TestCase):
    __module__ = __name__

    def setUp(self):
        self.old_INSTALLED_APPS = settings.INSTALLED_APPS
        settings.INSTALLED_APPS += ['eventtools.tests.eventtools_testapp']
        load_app('eventtools.tests.eventtools_testapp')
        call_command('flush', verbosity=0, interactive=False)
        call_command('syncdb', verbosity=0, interactive=False)
        self.Occ1 = get_model('eventtools_testapp', 'lectureeventoccurrence')
        self.Occ2 = get_model('eventtools_testapp', 'broadcasteventoccurrence')
        self.Occ3 = get_model('eventtools_testapp', 'lessoneventoccurrence')
        self.occs = [self.Occ1, self.Occ2, self.Occ3]
        
        self.Gen1 = get_model('eventtools_testapp', 'lectureeventoccurrencegenerator')
        self.Gen2 = get_model('eventtools_testapp', 'broadcasteventoccurrencegenerator')
        self.Gen3 = get_model('eventtools_testapp', 'lessoneventoccurrencegenerator')
        self.gens = [self.Gen1, self.Gen2, self.Gen3]



    def tearDown(self):
        settings.INSTALLED_APPS = self.old_INSTALLED_APPS



    def test_model_metaclass_generation(self):
        """
        Test that when we create a subclass of EventBase, a corresponding subclass of OccurrenceBase is generated automatically
        """
        for (occ, gen,) in zip(self.occs, self.gens):
            #Check that for each EventBase model defined, an Occurrence and an OccurrenceGenerator are created.
            self.assertTrue((occ != None))
            self.assertTrue((gen != None))
            
            #...and that the right FKs are specified.
            self.assertTrue(isinstance(occ.generator, ReverseSingleRelatedObjectDescriptor)) #This is what ForeignKey becomes
            self.assertTrue(isinstance(gen.event, ReverseSingleRelatedObjectDescriptor))
            
            #...and that the occurrence model is linked properly to the generator
            self.assertEqual(gen._occurrence_model_name, occ.__name__.lower())


    def test_event_without_variation(self):
        """
        Events that have no variation class defined still work (and that it is not allowed to try to set a variation)
        """
        
        subject = 'Django testing for n00bs'
        lesson = LessonEvent.objects.create(subject=subject)
        gen = lesson.generators.create(first_start_date=date(2010, 1, 1), first_start_time=time(13, 0), first_end_date=None, first_end_time=time(14, 0))
        occ = lesson.get_one_occurrence()
        self.assertEqual(occ.varied_event, None)
        self.assertRaises(AttributeError, getattr, occ.varied_event, 'subject')
        self.assertRaises(AttributeError, setattr, occ, 'varied_event', 'foo')
        self.assertEqual(occ.unvaried_event.subject, subject)
        self.assertEqual(occ.merged_event.subject, subject)



    def test_event_occurrence_attributes(self):
        """Test that event occurrences can override (any) field of their parent event"""
        
        # Create an event, a generator, and get (the only possible) occurrence from the generator.
        te1 = LectureEvent.objects.create(location='The lecture hall', title='Lecture series on Butterflies')
        self.assertTrue(te1.wheelchair_access) # The original event has wheelchair access
        gen = te1.generators.create(first_start_date=date(2010, 1, 1), first_start_time=time(13, 0), first_end_date=None, first_end_time=time(14, 0))
        self.assertTrue(gen)
        occ = te1.get_one_occurrence()
        self.assertTrue(occ)
        
        #Test that the occurrence is the one we expect
        self.assertEqual(occ, models.get_model('eventtools_testapp', 'lectureeventoccurrence')(generator=gen, varied_start_date=date(2010, 1, 1), varied_start_time=time(13, 0), varied_end_date=None, varied_end_time=time(14, 0), unvaried_start_date=date(2010, 1, 1), unvaried_start_time=time(13, 0), unvaried_end_date=None, unvaried_end_time=time(14, 0)))

        #and that the occurrence's unvaried event shares properties with te1
        self.assertTrue(isinstance(occ.unvaried_event, LectureEvent))
        self.assertTrue(occ.unvaried_event.wheelchair_access)
        #and that the merged event is what we expect
        self.assertTrue(occ.merged_event.wheelchair_access)
        self.assertEqual(occ.merged_event.location, 'The lecture hall')
        
        #When first generated, there is no varied event for an occurrence.
        self.assertEqual(occ.varied_event, None)
        #So accessing a property raises AttributeError
        self.assertRaises(AttributeError, getattr, occ.varied_event, 'location')
        
        #Now create a variation with a different location
        occ.varied_event = LectureEventVariation.objects.create(location='The foyer')
        
        #Check the properties of the varied event, and that the merged event uses those to override the unvaried event
        self.assertEqual(occ.varied_event.location, 'The foyer')
        self.assertEqual(occ.unvaried_event.location, 'The lecture hall')
        self.assertEqual(occ.varied_event.wheelchair_access, None)

        self.assertEqual(occ.merged_event.location, 'The foyer')
        self.assertEqual(occ.merged_event.title, 'Lecture series on Butterflies')

        #Check that we can't write to merged event.
        self.assertRaises(Exception, setattr, occ.merged_event.location, "shouldn't be writeable")

        #Now update the title, location and wheelchair access of the varied event, and save the result.
        occ.varied_event.title = 'Butterflies I have known'
        occ.varied_event.location = 'The meeting room'
        occ.varied_event.wheelchair_access = False
        occ.varied_event.save()
        occ.save()
        
        #Check that the update merges correctly with the unvaried event
        self.assertTrue((occ.unvaried_event.title == 'Lecture series on Butterflies'))
        self.assertTrue((occ.varied_event.title == 'Butterflies I have known'))
        self.assertTrue((occ.merged_event.title == 'Butterflies I have known'))


        self.assertTrue((occ.unvaried_event.location == 'The lecture hall'))
        self.assertTrue((occ.varied_event.location == 'The meeting room'))
        self.assertTrue((occ.merged_event.location == 'The meeting room'))

        self.assertEqual(occ.unvaried_event.wheelchair_access, True)
        self.assertEqual(occ.varied_event.wheelchair_access, False)
        self.assertEqual(occ.merged_event.wheelchair_access, False)

        #Now update the title of the original event. The changes in the variation should persist.
        te1.title = 'Lecture series on Lepidoptera'
        te1.save()
        
        te1 = LectureEvent.objects.get(pk=te1.pk)
        occ = te1.get_one_occurrence() #from the database
        self.assertEqual(occ.unvaried_event.title, 'Lecture series on Lepidoptera')
        self.assertEqual(occ.merged_event.title, 'Butterflies I have known')
        self.assertEqual(occ.varied_event.title, 'Butterflies I have known')



    def test_saving(self):
        """
        A small check that saving occurrences without variations does not create a blank variation.
        TODO: expand this so to check changing the time of a (persistent) occurrence works the same way.
        """
        te1 = LectureEvent.objects.create(location='The lecture hall', title='Lecture series on Butterflies')
        te1.generators.create(first_start_date=date(2010, 1, 1), first_start_time=time(13, 0), first_end_date=None, first_end_time=time(14, 0))
        occ = te1.get_one_occurrence()
        num_variations1 = int(LectureEventVariation.objects.count())
        occ.save()
        num_variations2 = int(LectureEventVariation.objects.count())
        self.assertEqual(num_variations1, num_variations2)