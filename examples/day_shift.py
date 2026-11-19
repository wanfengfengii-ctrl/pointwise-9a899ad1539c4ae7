from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.batch import load
from issue.export import export
from issue.read import read_table
from ledger.database import open_database
from ledger.fields import FieldKey, get_field
from ledger.revisions import read_revisions
from returns.merge import AliasConflict
from returns.receipts import read_receipt
from returns.submit import submit


def show_case(case_id, inputs, expected, actual, downstream_expected, downstream_actual, paths, oracle):
    if actual != expected or downstream_actual != downstream_expected:
        raise AssertionError((case_id, actual, downstream_actual))
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': inputs,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': paths,
        'oracle': oracle,
    }, ensure_ascii=False))


def values(table):
    return [cell.value for cell in table.cells]


def main():
    with Path(__file__).with_name('batch.json').open(encoding='utf-8') as source:
        batch = json.load(source)
    batch_id = batch['batch_id']
    primary, backup = FieldKey(batch_id, 'P'), FieldKey(batch_id, 'S')
    edits = [
        {'row': 'A', 'cell': 'effective', 'value_um': 19},
        {'row': 'B', 'cell': 'direct', 'value_um': 21},
    ]
    with TemporaryDirectory(prefix='coating-shift-') as folder:
        path = Path(folder) / 'shift.sqlite'
        with closing(open_database(path)) as db:
            registration = load(db, batch)
            issued = export(db, batch_id)
            if values(issued) != [0, 17, None, 17]:
                raise AssertionError('Unexpected first shift table')
        with closing(open_database(path)) as db:
            try:
                submit(db, issued.table_id, edits)
            except AliasConflict:
                status = 'conflict'
            else:
                raise AssertionError('ALIAS_CONFLICT_ACCEPTED')
            p_state, s_state = get_field(db, primary), get_field(db, backup)
            receipt_count, = db.execute('SELECT count(*) FROM return_receipts').fetchone()
            show_case(
                'v6', {'P': None, 'S': 17, 'edits': edits}, 'conflict', status,
                [None, 0, 17, 0, 0],
                [p_state.value, p_state.revision, s_state.value, s_state.revision, receipt_count],
                ['issue/export.py', 'issue/store.py', 'returns/eligibility.py', 'returns/merge.py', 'returns/submit.py'],
                'A skips null P and reads S. B reads S directly. Disagreeing edits leave both fields and receipts unchanged.',
            )
            agreed = [edits[0], dict(edits[1], value_um=19)]
            applied = submit(db, issued.table_id, agreed)
        with closing(open_database(path)) as db:
            old_table = read_table(db, issued.table_id)
            receipt = read_receipt(db, applied.receipt_id)
            new_table = export(db, batch_id)
            replayed = load(db, batch)
            if old_table != issued or receipt != applied or new_table.table_id == issued.table_id:
                raise AssertionError('Fixed shift records did not survive reopening')
            show_case(
                'v5', {'table': issued.table_id, 'edits': agreed},
                {'field_count': 1, 'changes': [['S', 19, 1]]},
                {'field_count': receipt.field_count,
                 'changes': [[item.key.field_id, item.value, item.revision] for item in receipt.changes]},
                {'old': [0, 17, None, 17], 'new': [0, 19, None, 19], 'history': [17, 19],
                 'same_registration': True, 'current_after_reload': 19},
                {'old': values(old_table), 'new': values(new_table),
                 'history': [state.value for state in read_revisions(db, backup)],
                 'same_registration': replayed == registration, 'current_after_reload': get_field(db, backup).value},
                ['returns/submit.py', 'ledger/commit.py', 'returns/receipts.py', 'issue/read.py', 'issue/export.py', 'intake/batch.py'],
                'Hand calculation leaves C at zero and D empty. A and B share one change to S. The original registration still describes S at 17.',
            )


if __name__ == '__main__':
    main()
