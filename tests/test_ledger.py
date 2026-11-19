from intake.batch import load
from ledger.changes import FieldChange
from ledger.commit import correct, write_corrections
from ledger.database import write_transaction
from ledger.fields import FieldKey, StaleRevision, get_field
from tests.scenario_fixtures import BATCH_ID, LabCase, sample_batch


class TestLedger(LabCase):
    def setUp(self):
        super().setUp()
        self.register()

    def test_correct_reject(self):
        before = self.account()
        with self.assertRaises(KeyError):
            correct(self.db, BATCH_ID, 'unknown', 0, 10)
        with self.assertRaises(StaleRevision):
            correct(self.db, BATCH_ID, 'S', 1, 10)
        for revision, value in ((0, False), (0, 2.0), (0, '2'), (False, 2), (-1, 2)):
            with self.subTest(revision=revision, value=value):
                with self.assertRaises(ValueError):
                    correct(self.db, BATCH_ID, 'S', revision, value)
        self.assertEqual(self.account(), before)

    def test_empty_round_trip_keeps_history(self):
        correct(self.db, BATCH_ID, 'P', 0, 17)
        correct(self.db, BATCH_ID, 'P', 1, None)
        self.reopen()
        self.assertEqual([(item.value, item.revision) for item in self.history('P')], [(None, 0), (17, 1), (None, 2)])
        with self.assertRaises(StaleRevision):
            correct(self.db, BATCH_ID, 'P', 0, 17)
        self.assertEqual(self.field('P').revision, 2)

    def test_write_set_is_validated_before_writing(self):
        before = self.account()
        p, s = FieldKey(BATCH_ID, 'P'), FieldKey(BATCH_ID, 'S')
        for extra in (FieldChange(p, 0, 9), FieldChange(s, 1, 9), FieldChange(FieldKey('other', 'S'), 0, 9)):
            with self.subTest(extra=extra):
                with write_transaction(self.db):
                    with self.assertRaises(ValueError):
                        write_corrections(self.db, BATCH_ID, [FieldChange(p, 0, 2), extra])
                    self.assertEqual(self.account(), before)

    def test_batches_with_identical_field_names_are_isolated(self):
        payload = sample_batch()
        payload['batch_id'] = 'CW-28'
        load(self.db, payload)
        correct(self.db, BATCH_ID, 'S', 0, 19)
        second = get_field(self.db, FieldKey('CW-28', 'S'))
        self.assertEqual((self.field('S').value, second.value, second.revision), (19, 17, 0))

    def test_exact_integer_values_persist(self):
        large = 2 ** 100 + 11
        correct(self.db, BATCH_ID, 'P', 0, large)
        correct(self.db, BATCH_ID, 'P', 1, -large)
        self.reopen()
        self.assertEqual(self.field('P').value, -large)
        self.assertEqual([state.value for state in self.history('P')], [None, large, -large])
