import sqlite3

from issue.export import export
from issue.read import read_table
from ledger.commit import correct
from returns.eligibility import InvalidCell, StaleEdit
from returns.merge import AliasConflict
from returns.receipts import read_receipt
from returns.submit import submit
from tests.scenario_fixtures import BATCH_ID, LabCase, edit, install_commit_failure, install_receipt_write_failure


class TestReturns(LabCase):
    def setUp(self):
        super().setUp()
        self.register()

    def test_alias_same_value(self):
        original = export(self.db, BATCH_ID)
        self.reopen()
        receipt = submit(self.db, original.table_id, [edit('A', 19), edit('B', 19, 'direct')])
        self.assertEqual((receipt.table_id, receipt.field_count), (original.table_id, 1))
        self.assertEqual([(change.key.field_id, change.value, change.revision) for change in receipt.changes],
                         [('S', 19, 1)])
        self.assertEqual([(state.value, state.revision) for state in self.history('S')], [(17, 0), (19, 1)])
        self.assertEqual((self.field('P').value, self.field('P').revision), (None, 0))
        self.assertEqual(self.counts('return_receipts', 'receipt_fields'), (1, 1))
        self.reopen()
        self.assertEqual(read_receipt(self.db, receipt.receipt_id), receipt)
        self.assertEqual(read_table(self.db, original.table_id), original)
        self.assertEqual([cell.value for cell in original.cells], [0, 17, None, 17])
        self.assertEqual([cell.value for cell in export(self.db, BATCH_ID).cells], [0, 19, None, 19])

    def test_alias_conflict(self):
        issued = export(self.db, BATCH_ID)
        self.reopen()
        before = self.account()
        self.assertEqual([cell.value for cell in issued.cells], [0, 17, None, 17])
        for items in ([edit('A', 19), edit('B', 21, 'direct')],
                      [edit('B', 21, 'direct'), edit('A', 19)]):
            with self.subTest(items=items):
                try:
                    submit(self.db, issued.table_id, items)
                except AliasConflict:
                    pass
                else:
                    self.fail('ALIAS_CONFLICT_ACCEPTED')
                self.assertEqual(self.account(), before)
        self.reopen()
        self.assertEqual(self.account(), before)
        self.assertEqual((self.field('P').value, self.field('S').value), (None, 17))
        self.assertEqual(self.counts('return_receipts', 'receipt_fields'), (0, 0))
        self.assertEqual(read_table(self.db, issued.table_id), issued)

    def test_distinct_equal_display_values(self):
        correct(self.db, BATCH_ID, 'P', 0, 17)
        table = export(self.db, BATCH_ID)
        self.assertEqual([cell.value for cell in table.cells], [0, 17, None, 17])
        receipt = submit(self.db, table.table_id, [edit('B', 21, 'direct'), edit('A', 19)])
        self.assertEqual(receipt.field_count, 2)
        self.assertEqual([(state.key.field_id, state.value, state.revision) for state in receipt.changes],
                         [('P', 19, 2), ('S', 21, 1)])
        self.assertEqual([cell.value for cell in export(self.db, BATCH_ID).cells], [0, 19, None, 21])

    def test_stale_fallback(self):
        original = export(self.db, BATCH_ID)
        correct(self.db, BATCH_ID, 'P', 0, 17)
        for stage in ('same-value switch', 'empty round trip'):
            with self.subTest(stage=stage):
                if stage == 'empty round trip':
                    correct(self.db, BATCH_ID, 'P', 1, None)
                self.reopen()
                current = export(self.db, BATCH_ID)
                self.assertEqual([cell.value for cell in current.cells], [0, 17, None, 17])
                before = self.account()
                with self.assertRaises(StaleEdit):
                    submit(self.db, original.table_id, [edit('B', 19, 'direct'), edit('A', 19)])
                self.assertEqual(self.account(), before)
                self.assertEqual(read_table(self.db, original.table_id), original)
        self.assertEqual(self.field('P').revision, 2)
        self.assertEqual(self.field('S').value, 17)

    def test_selected_field_revision_is_checked_even_at_same_value(self):
        table = export(self.db, BATCH_ID)
        correct(self.db, BATCH_ID, 'S', 0, 17)
        before = self.account()
        with self.assertRaises(StaleEdit):
            submit(self.db, table.table_id, [edit('B', 19, 'direct')])
        self.assertEqual(self.account(), before)

    def test_unrelated_update(self):
        table = export(self.db, BATCH_ID)
        correct(self.db, BATCH_ID, 'CS', 0, 27)
        receipt = submit(self.db, table.table_id, [edit('C', 9)])
        self.assertEqual(receipt.field_count, 1)
        self.assertEqual((self.field('CP').value, self.field('CP').revision), (9, 1))
        self.assertEqual((self.field('CS').value, self.field('CS').revision), (27, 1))

    def test_untouched_direct_cell(self):
        correct(self.db, BATCH_ID, 'P', 0, 0)
        table = export(self.db, BATCH_ID)
        correct(self.db, BATCH_ID, 'S', 0, 25)
        self.reopen()
        receipt = submit(self.db, table.table_id, [edit('A', 23)])
        self.assertEqual(receipt.field_count, 1)
        self.assertEqual((self.field('P').value, self.field('P').revision), (23, 2))
        self.assertEqual((self.field('S').value, self.field('S').revision), (25, 1))

    def test_failed_commit(self):
        table = export(self.db, BATCH_ID)
        old_receipt = submit(self.db, table.table_id, [edit('C', 3)])
        before = self.account()
        install_commit_failure(self.db, 'return_receipts')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
            submit(self.db, table.table_id, [edit('A', 20), edit('B', 20, 'direct')])
        self.assertFalse(self.db.in_transaction)
        self.reopen()
        self.assertEqual(self.account(), before)
        self.assertEqual(self.counts('commit_children'), (0,))
        self.assertEqual(read_table(self.db, table.table_id), table)
        self.assertEqual(read_receipt(self.db, old_receipt.receipt_id), old_receipt)

    def test_receipt_write_failure(self):
        table = export(self.db, BATCH_ID)
        old_receipt = submit(self.db, table.table_id, [edit('C', 3)])
        before = self.account()
        install_receipt_write_failure(self.db)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'fixture receipt detail rejected'):
            submit(self.db, table.table_id, [edit('A', 20)])
        self.reopen()
        self.assertEqual(self.account(), before)
        self.assertEqual(read_table(self.db, table.table_id), table)
        self.assertEqual(read_receipt(self.db, old_receipt.receipt_id), old_receipt)

    def test_blank_cell(self):
        table = export(self.db, BATCH_ID)
        before = self.account()
        for items in ([edit('D', 15)], [edit('A', 19), edit('D', 15)]):
            with self.subTest(items=items):
                with self.assertRaisesRegex(InvalidCell, 'Blank cell'):
                    submit(self.db, table.table_id, items)
                self.assertEqual(self.account(), before)

    def test_invalid_requests_do_not_write(self):
        table = export(self.db, BATCH_ID)
        before = self.account()
        for items in ([], [edit('A', 19), edit('missing', 1)],
                      [edit('A', 19), edit('B', 19)], [edit('A', True)], [edit('A', 19.0)], [edit('A', '19')]):
            with self.subTest(items=items):
                with self.assertRaises(ValueError):
                    submit(self.db, table.table_id, items)
                self.assertEqual(self.account(), before)
        with self.assertRaises(KeyError):
            submit(self.db, 500, [edit('A', 19)])
        self.assertEqual(self.account(), before)

    def test_touched_cell_requires_issuance_reference(self):
        table = export(self.db, BATCH_ID)
        self.db.execute('UPDATE issued_cells SET reference_json = NULL WHERE table_id = ? AND row_name = ?',
                        (table.table_id, 'A'))
        self.reopen()
        self.assertEqual(read_table(self.db, table.table_id), table)
        before = self.account()
        with self.assertRaisesRegex(InvalidCell, 'no applicable issuance reference'):
            submit(self.db, table.table_id, [edit('B', 19, 'direct'), edit('A', 19)])
        self.assertEqual(self.account(), before)

    def test_receipt_after_later_correction(self):
        table = export(self.db, BATCH_ID)
        big = 2 ** 104 + 1
        receipt = submit(self.db, table.table_id, [edit('B', -big, 'direct')])
        current = export(self.db, BATCH_ID)
        self.assertEqual([cell.value for cell in current.cells], [0, -big, None, -big])
        correct(self.db, BATCH_ID, 'S', 1, 25)
        self.reopen()
        self.assertEqual(read_receipt(self.db, receipt.receipt_id), receipt)
        self.assertEqual((receipt.changes[0].value, receipt.changes[0].revision), (-big, 1))
        self.assertEqual(read_table(self.db, current.table_id), current)
        with self.assertRaises(KeyError):
            read_receipt(self.db, 300)
