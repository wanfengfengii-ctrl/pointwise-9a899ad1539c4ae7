import sqlite3

from intake.batch import load
from intake.origins import read_origins
from intake.parse import DeviceReading
from intake.registration import find_registration
from ledger.commit import correct
from ledger.fields import has_field_scope
from tests.scenario_fixtures import BATCH_ID, LabCase, install_commit_failure, sample_batch


class TestIntake(LabCase):
    def test_load_and_initialize_again(self):
        receipt = self.register()
        self.assertEqual(receipt.field_count, 6)
        self.assertEqual((self.field('S').value, self.field('S').revision), (17, 0))
        initial = read_origins(self.db, BATCH_ID)
        self.assertIn(DeviceReading('S', 'station-4-backup', 17), initial)
        self.assertIn(DeviceReading('P', 'station-4-primary', None), initial)
        correct(self.db, BATCH_ID, 'S', 0, 19)
        self.reopen()
        payload = sample_batch()
        payload['readings'].append(dict(payload['readings'][0]))
        payload['readings'].reverse()
        self.assertEqual(load(self.db, payload), receipt)
        self.assertEqual(find_registration(self.db, BATCH_ID), receipt)
        self.assertEqual(read_origins(self.db, BATCH_ID), initial)
        self.assertEqual((self.field('S').value, self.field('S').revision), (19, 1))
        self.assertEqual([(item.revision, item.value) for item in self.history('S')], [(0, 17), (1, 19)])
        self.assertEqual(self.counts('registrations', 'field_scopes', 'fields', 'device_origins', 'field_revisions'),
                         (1, 1, 6, 6, 7))

    def test_conflicting_source_rejected(self):
        for changed in ({'device': 'another-station'}, {'value_um': 99}):
            for reverse in (False, True):
                with self.subTest(changed=changed, reverse=reverse):
                    payload = sample_batch()
                    payload['readings'].append(dict(payload['readings'][0], **changed))
                    if reverse:
                        payload['readings'].reverse()
                    with self.assertRaisesRegex(ValueError, 'Conflicting device records'):
                        load(self.db, payload)
                    self.assertIsNone(find_registration(self.db, BATCH_ID))
                    self.assertFalse(has_field_scope(self.db, BATCH_ID))
                    self.assertEqual(self.counts('registrations', 'fields', 'device_origins', 'field_revisions'), (0, 0, 0, 0))

    def test_invalid_value(self):
        for value in (True, 17.0, '17', []):
            with self.subTest(value=value):
                payload = sample_batch()
                payload['readings'][-1]['value_um'] = value
                with self.assertRaisesRegex(ValueError, 'integer micrometres'):
                    load(self.db, payload)
                self.assertEqual(self.counts('registrations', 'field_scopes', 'fields', 'device_origins'), (0, 0, 0, 0))

    def test_existing_batch_conflict(self):
        receipt = self.register()
        correct(self.db, BATCH_ID, 'S', 0, 19)
        before = self.account()
        originals = read_origins(self.db, BATCH_ID)
        for changed in ({'device': 'another-station'}, {'value_um': 19}):
            with self.subTest(changed=changed):
                payload = sample_batch()
                payload['readings'][0].update(changed)
                with self.assertRaisesRegex(ValueError, 'original registration'):
                    load(self.db, payload)
                self.assertEqual(self.account(), before)
                self.assertEqual(read_origins(self.db, BATCH_ID), originals)
                self.assertEqual(find_registration(self.db, BATCH_ID), receipt)

    def test_failed_registration_commit(self):
        install_commit_failure(self.db, 'registrations')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
            self.register()
        self.assertFalse(self.db.in_transaction)
        self.reopen()
        self.assertEqual(self.counts('registrations', 'field_scopes', 'fields', 'device_origins',
                                     'field_revisions', 'commit_children'), (0, 0, 0, 0, 0, 0))
