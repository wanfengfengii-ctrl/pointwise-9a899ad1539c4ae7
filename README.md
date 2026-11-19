# 澄湾涂层检测交班账

设备工位按批交付探头原值和设备来源。白班质控员用清册发行固定勘误表，将复测值按表号和具名格回传。夜班用旧表、成功回执和新发行表核对当班所见、实际入账和当前有效读值。

需要 Python 3.11 和标准库自带的 SQLite。以下命令在项目根目录执行。

```sh
python3 -B check_project.py
python3 -B -m examples.day_shift
```

第一条命令是发行环境提供的完整回归入口。演示在独立临时数据库中登记、发行、处理两批回传、重开领取、复出表并重跑登记。任一核对失败都会以异常退出。

## 班次样例

1. 设备提供 `examples/batch.json` 中的原读值及设备来源。白班登记后得到固定登记回执。原字段修订从 0 开始。
2. 白班按 `examples/roster.json` 的顺序发行表。C 的主值为 0，A 跳过空主字段 P 取备用 S 的 17，D 主备皆空，B 直接读 S。表依次显示 `0, 17, 空, 17`。
3. 白班将 A 的有效格改为 19、B 的直接格改为 21。两格指向同一个原字段 S，整批拒绝，P 仍为空，S 仍为 17。
4. 复测确认两格均为 19 后，白班按同一旧表回传。S 只增加一个修订，回执计数为 1。
5. 夜班重开后按号领取旧表和回执，再发行新表，得到 `0, 19, 空, 19`。重复登记样例仍返回原登记回执，S 保持 19。

## Python 接口

调用方通过 `ledger.database.open_database(path)` 打开数据库，结束时关闭连接。公开业务调用各自建立事务，传入连接应处于空闲状态。以位置参数调用以下接口。

| 模块 | 调用 | 结果 |
| --- | --- | --- |
| `intake.batch` | `load(db, payload)` | `RegistrationReceipt`，包含 `registration_id`、`batch_id`、`field_count` |
| `ledger.commit` | `correct(db, batch_id, field_id, expected_revision, value)` | 更新后的 `FieldState`，包含 `key`、`revision`、`value` |
| `issue.export` | `export(db, batch_id)` | `TableView`，包含 `table_id`、`batch_id` 和有序 `cells` |
| `issue.read` | `read_table(db, table_id)` | 同一固定 `TableView` |
| `returns.submit` | `submit(db, table_id, edits)` | `Receipt`，包含 `receipt_id`、`table_id`、有序 `changes` 和 `field_count` |
| `returns.receipts` | `read_receipt(db, receipt_id)` | 同一固定 `Receipt` |

批次输入是含 `batch_id` 和非空 `readings` 的对象，也接受其 JSON 文本。每条记录含 `field`、`device`、`value_um`。标识区分大小写。批内完全相同的重复记录归为一条，值或来源冲突时整批拒绝。重跑登记按最初记录比较，后续更正保留。`intake.origins.read_origins` 可读取原始来源与登记值，`ledger.revisions.read_revisions` 可按 `FieldKey` 查看修订历史。

默认发行使用样例中的实验室清册。其他批次可用 `views.roster.build_roster(payload)` 解析清册，再用 `export(db, batch_id, roster=roster)` 发行。清册采用 `rows` 数组，每行含 `row`、`cells`。每个格有 `cell`、`kind`。`effective` 格另含不同的 `primary` 和 `backup` 字段号，`direct` 格另含一个 `field`。行名和行内格名唯一。显示格带 `address`、从零开始的 `row_index` 和 `cell_index`、`value`，以及清册所列主字段或直接字段 `nominal_field`。回传资格由表中冻结的实际选源决定。

回传 `edits` 是非空列表，每项形如 `{"row": "A", "cell": "effective", "value_um": 19}`。同一格可以出现多次，各项均参与资格核对和归并。读值单位为整数微米，保留符号和零。登记和 `correct` 接受 `None` 表示空，回传只接受整数。布尔值、浮点值和数值文本均不作整数接受。候选按主备顺序读取到第一个非空值为止。缺失的候选字段使整表发行失败。

回传遇到未知格、全空格、缺失资格记录、过期读取链或同源异值时整批拒绝。发行时跳过的空字段也参与修订检查。主字段补成和备用相同的值再改回空，旧有效格仍过期。只变更未触及的格或命中后未读取的候选字段时，相关旧格仍可回传。成功回执保存实际入账的原字段、值及修订，同值别名只计一笔。事务失败时账、字段历史和回执一起回滚。按号领取的旧表和旧回执保持原内容。

输入或业务拒绝抛出 `ValueError` 或其子类。不存在的批、字段、表号或回执号抛出 `KeyError`。SQLite 错误由调用方按异常处理。成功返回意味着所在业务事务已提交。
