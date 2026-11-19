import sqlite3

from issue.export import export
from issue.read import read_table
from ledger.commit import correct
from tests.scenario_fixtures import BATCH_ID, LabCase, displayed, install_commit_failure
from views.roster import build_roster


class TestIssue(LabCase):
    def setUp(self):
        super().setUp()
        self.register()

    def test_zero_and_blank(self):
        issued = export(self.db, BATCH_ID)
        self.assertEqual(displayed(issued), [('C', 'effective', 0), ('A', 'effective', 17),
                                           ('D', 'effective', None), ('B', 'direct', 17)])
        self.reopen()
        self.assertEqual(read_table(self.db, issued.table_id), issued)

    def test_frozen_read(self):
        original = export(self.db, BATCH_ID)
        correct(self.db, BATCH_ID, 'S', 0, 19)
        self.reopen()
        current = export(self.db, BATCH_ID)
        self.assertNotEqual(current.table_id, original.table_id)
        self.assertEqual(read_table(self.db, original.table_id), original)
        self.assertEqual([cell.value for cell in original.cells], [0, 17, None, 17])
        self.assertEqual([cell.value for cell in current.cells], [0, 19, None, 19])

    def test_stable_order(self):
        roster = build_roster({'rows': [
            {'row': 'Z', 'cells': [
                {'cell': 'z', 'kind': 'direct', 'field': 'S'},
                {'cell': 'a', 'kind': 'direct', 'field': 'CP'},
            ]},
            {'row': 'A', 'cells': [{'cell': 'x', 'kind': 'direct', 'field': 'DP'}]},
        ]})
        table = export(self.db, BATCH_ID, roster=roster)
        self.reopen()
        readback = read_table(self.db, table.table_id)
        self.assertEqual(displayed(readback), [('Z', 'z', 17), ('Z', 'a', 0), ('A', 'x', None)])
        self.assertEqual([(cell.row_index, cell.cell_index) for cell in readback.cells], [(0, 0), (0, 1), (1, 0)])

    def test_missing_source(self):
        for primary, backup in (('missing', 'S'), ('CP', 'missing')):
            with self.subTest(primary=primary, backup=backup):
                roster = build_roster({'rows': [{'row': 'X', 'cells': [
                    {'cell': 'effective', 'kind': 'effective', 'primary': primary, 'backup': backup},
                ]}]})
                with self.assertRaisesRegex(KeyError, 'missing'):
                    export(self.db, BATCH_ID, roster=roster)
        self.assertEqual(self.counts('issued_tables', 'issued_cells'), (0, 0))

    def test_ambiguous_roster(self):
        cell = {'cell': 'X', 'kind': 'direct', 'field': 'S'}
        single = {'row': 'A', 'cells': [cell]}
        for rows in ([single, single], [{'row': 'A', 'cells': [cell, cell]}]):
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(ValueError, 'Duplicate'):
                    export(self.db, BATCH_ID, roster=build_roster({'rows': rows}))
        self.assertEqual(self.counts('issued_tables', 'issued_cells'), (0, 0))

    def test_unknown_table_and_batch(self):
        with self.assertRaises(KeyError):
            read_table(self.db, 50)
        with self.assertRaises(KeyError):
            export(self.db, 'absent')
        self.assertEqual(self.counts('issued_tables', 'issued_cells'), (0, 0))

    def test_failed_export(self):
        original = export(self.db, BATCH_ID)
        install_commit_failure(self.db, 'issued_tables')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
            export(self.db, BATCH_ID)
        self.assertFalse(self.db.in_transaction)
        self.reopen()
        self.assertEqual(self.counts('issued_tables', 'issued_cells', 'commit_children'), (1, 4, 0))
        self.assertEqual(read_table(self.db, original.table_id), original)
