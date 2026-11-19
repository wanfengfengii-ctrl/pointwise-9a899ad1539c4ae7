from ledger.changes import FieldChange
from ledger.fields import FieldKey
from returns.eligibility import QualifiedEdit


class AliasConflict(ValueError):
    pass


def merge_edits(edits: tuple[QualifiedEdit, ...]) -> tuple[FieldChange, ...]:
    by_target: dict[FieldKey, QualifiedEdit] = {}
    for edit in edits:
        previous = by_target.get(edit.target)
        if previous is None:
            by_target[edit.target] = edit
        elif previous.value != edit.value:
            raise AliasConflict(f'{previous.address!r} and {edit.address!r} disagree for {edit.target.field_id!r}')
        elif previous.expected_revision != edit.expected_revision:
            raise ValueError(f'Inconsistent issuance revision for {edit.target.field_id!r}')
    return tuple(FieldChange(key, by_target[key].expected_revision, by_target[key].value) for key in sorted(by_target))
