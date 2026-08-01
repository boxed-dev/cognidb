"""Major-release pipeline: policy, allowlist, repair, linking."""

from cognidb.pipeline.secure_query import SecureQueryPipeline
from cognidb.security import (
    QuerySecurityValidator,
    InputSanitizer,
    AccessController,
    StatementMode,
    StatementPolicy,
)
from cognidb.ai.fake_generator import FakeSQLGenerator


class _Drv:
    def __init__(self, fail_first=False):
        self.fail_first = fail_first
        self.n = 0
        self.calls = []

    def execute_native_query(self, query, params=None):
        self.n += 1
        self.calls.append(query)
        if self.fail_first and self.n == 1:
            raise RuntimeError("no such table: order")
        return [{"ok": 1}]


def _pipe(sql, *, policy=None, access=None, enable_ac=False, gen=None, drv=None, schema=None):
    return SecureQueryPipeline(
        driver=drv or _Drv(),
        generator=gen or FakeSQLGenerator(sql),
        validator=QuerySecurityValidator(allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE"]),
        sanitizer=InputSanitizer(),
        schema=schema or {"users": {"id": "int", "name": "text"}, "orders": {"id": "int"}},
        access_controller=access,
        enable_access_control=enable_ac,
        enable_audit=False,
        policy=policy or StatementPolicy(),
        generation_mode="free_form",
        allow_dangerous_sql=True,
        repair_budget=1,
    )


def test_read_mode_blocks_delete():
    r = _pipe("DELETE FROM users").run("remove users")
    assert r.success is False
    assert "not allowed" in (r.error or "").lower() or "Forbidden" in (r.error or "") or "DELETE" in (r.error or "")


def test_write_mode_allows_delete():
    policy = StatementPolicy(mode=StatementMode.WRITE)
    r = _pipe("DELETE FROM users WHERE id=1", policy=policy).run("remove user")
    assert r.success is True


def test_ddl_blocked_even_in_write_mode():
    policy = StatementPolicy(mode=StatementMode.WRITE)
    r = _pipe("DROP TABLE users", policy=policy).run("drop users")
    assert r.success is False


def test_allowlist_denies_table():
    ac = AccessController()
    ac.create_read_only_user("analyst", ["orders"])
    r = _pipe(
        "SELECT * FROM users",
        access=ac,
        enable_ac=True,
    ).run("show users", user_id="analyst")
    assert r.success is False
    assert "Access denied" in (r.error or "")


def test_allowlist_allows_table():
    ac = AccessController()
    ac.create_read_only_user("analyst", ["users"])
    r = _pipe(
        "SELECT id FROM users",
        access=ac,
        enable_ac=True,
    ).run("list users", user_id="analyst")
    assert r.success is True


def test_repair_once():
    gen = FakeSQLGenerator("SELECT * FROM order", repair_sql="SELECT * FROM orders")
    drv = _Drv(fail_first=True)
    r = _pipe("SELECT * FROM order", gen=gen, drv=drv).run("orders please")
    assert r.success is True
    assert r.repaired is True
    assert gen.repair_calls == 1


def test_schema_linking_picks_orders():
    from cognidb.schema.linking import link_schema
    schema = {
        "users": {"id": "int"},
        "orders": {"id": "int", "total": "int"},
        "warehouse_inventory_snapshot": {"sku": "text"},
    }
    linked, strategy = link_schema("total orders last week", schema, top_k=2)
    assert strategy == "linked"
    assert "orders" in linked
