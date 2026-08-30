"""Normalize legacy model points into global points."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260817_0002"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _sensor_unit(value: object) -> str:
    """保留已有非空单位快照，NULL/空白统一为无单位空字符串。"""
    if not isinstance(value, str) or not value.strip():
        return ""
    return value


def _create_point_table() -> None:
    op.create_table(
        "point",
        sa.Column("point_id", sa.String(100), primary_key=True, nullable=False),
        sa.Column("point_name", sa.String(20), nullable=False),
        sa.Column("point_unit", sa.String(10), nullable=False),
        sa.Column("point_description", sa.String(200), nullable=True),
        sa.UniqueConstraint("point_name", "point_unit", name="uq_point_name_unit"),
    )


def _create_model_point_table() -> None:
    op.create_table(
        "model_point",
        sa.Column(
            "model_id",
            sa.String(100),
            sa.ForeignKey("model.model_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "point_id",
            sa.String(100),
            sa.ForeignKey("point.point_id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        ),
    )


def _create_sensor_point_table() -> None:
    op.create_table(
        "sensor_point",
        sa.Column("point_id", sa.String(100), primary_key=True, nullable=False),
        sa.Column("sensor_id", sa.String(100), nullable=False),
        sa.Column("source_model_id", sa.String(100), nullable=False),
        sa.Column("source_point_id", sa.String(100), nullable=False),
        sa.Column("point_name", sa.String(20), nullable=False),
        sa.Column("point_unit", sa.String(10), nullable=False),
        sa.Column("json_path", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_model_id", "source_point_id"],
            ["model_point.model_id", "model_point.point_id"],
            name="fk_sensor_point_source_model_point",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_sensor_point_source_point_id",
        "sensor_point",
        ["source_point_id"],
    )
    op.create_index(
        "ix_sensor_point_source_model_point",
        "sensor_point",
        ["source_model_id", "source_point_id"],
    )


def _rename_postgresql_constraint(table: str, old_name: str, new_name: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Fresh databases are already created in the final form by the baseline.
    if "sensor_model" not in tables:
        required = {"model", "point", "model_point", "sensor_point"}
        if not required.issubset(tables):
            raise RuntimeError("database is neither the legacy nor normalized schema")
        return

    models = {
        row.model_id
        for row in bind.execute(sa.text("SELECT model_id FROM sensor_model"))
    }
    invalid_model_id = next((model_id for model_id in models if not _is_uuid(model_id)), None)
    if invalid_model_id is not None:
        raise RuntimeError(f"sensor_model has non-UUID model_id: {invalid_model_id}")
    legacy_model_points = list(
        bind.execute(
            sa.text(
                "SELECT point_id, model_id, point_name, point_unit "
                "FROM model_point ORDER BY point_id"
            )
        ).mappings()
    )
    legacy_sensor_points = list(
        bind.execute(
            sa.text(
                "SELECT point_id, sensor_id, model_point_id, point_name, point_unit, json_path "
                "FROM sensor_point ORDER BY point_id"
            )
        ).mappings()
    )
    referenced_model_point_ids = {
        row["model_point_id"] for row in legacy_sensor_points
    }

    old_model_point_by_id: dict[str, sa.RowMapping] = {}
    grouped: dict[tuple[str, str], list[sa.RowMapping]] = defaultdict(list)
    for row in legacy_model_points:
        if not _is_uuid(row["point_id"]):
            raise RuntimeError(f"model_point has non-UUID point_id: {row['point_id']}")
        if row["model_id"] not in models:
            if row["point_id"] in referenced_model_point_ids:
                raise RuntimeError(
                    "referenced model_point has invalid model_id: "
                    f"{row['point_id']} -> {row['model_id']}"
                )
            # 旧库可能遗留型号已删除、且没有任何实例测点引用的孤立绑定。
            # 这类记录不承载可用业务数据，不迁移到新结构。
            continue
        name = row["point_name"].strip() if isinstance(row["point_name"], str) else ""
        # 旧库允许 NULL 单位；新结构统一用空字符串表示无单位，保证组合唯一。
        unit = row["point_unit"].strip() if isinstance(row["point_unit"], str) else ""
        if not name:
            raise RuntimeError(f"model_point has blank name: {row['point_id']}")
        normalized = dict(row)
        normalized["point_name"] = name
        normalized["point_unit"] = unit
        old_model_point_by_id[row["point_id"]] = normalized
        grouped[(name, unit)].append(normalized)

    sensor_point_ids: set[str] = set()
    for row in legacy_sensor_points:
        if not _is_uuid(row["point_id"]):
            raise RuntimeError(f"sensor_point has non-UUID point_id: {row['point_id']}")
        if row["point_id"] in sensor_point_ids:
            raise RuntimeError(f"sensor_point has duplicate point_id: {row['point_id']}")
        sensor_point_ids.add(row["point_id"])
        if row["model_point_id"] not in old_model_point_by_id:
            raise RuntimeError(f"sensor_point has invalid model_point_id: {row['point_id']}")
        if not isinstance(row["point_name"], str) or not row["point_name"].strip():
            raise RuntimeError(f"sensor_point has blank point_name: {row['point_id']}")

    if "measurement" in tables:
        missing_measurement_point = bind.scalar(
            sa.text(
                "SELECT m.point_id FROM measurement m "
                "LEFT JOIN sensor_point sp ON sp.point_id = m.point_id "
                "WHERE sp.point_id IS NULL LIMIT 1"
            )
        )
        if missing_measurement_point is not None:
            raise RuntimeError(
                f"measurement has no matching sensor_point: {missing_measurement_point}"
            )

    canonical_by_key = {
        key: min(row["point_id"] for row in rows)
        for key, rows in grouped.items()
    }
    canonical_by_old_id = {
        row["point_id"]: canonical_by_key[(row["point_name"], row["point_unit"])]
        for row in old_model_point_by_id.values()
    }

    op.rename_table("sensor_model", "model")
    op.rename_table("model_point", "model_point_legacy")
    op.rename_table("sensor_point", "sensor_point_legacy")
    _rename_postgresql_constraint("model", "sensor_model_pkey", "model_pkey")
    _rename_postgresql_constraint(
        "model_point_legacy", "model_point_pkey", "model_point_legacy_pkey"
    )
    _rename_postgresql_constraint(
        "sensor_point_legacy", "sensor_point_pkey", "sensor_point_legacy_pkey"
    )
    _create_point_table()
    _create_model_point_table()
    _create_sensor_point_table()

    if grouped:
        bind.execute(
            sa.text(
                "INSERT INTO point (point_id, point_name, point_unit, point_description) "
                "VALUES (:point_id, :point_name, :point_unit, NULL)"
            ),
            [
                {
                    "point_id": canonical_by_key[key],
                    "point_name": key[0],
                    "point_unit": key[1],
                }
                for key in sorted(grouped)
            ],
        )

    bindings = sorted(
        {
            (row["model_id"], canonical_by_old_id[row["point_id"]])
            for row in old_model_point_by_id.values()
        }
    )
    if bindings:
        bind.execute(
            sa.text(
                "INSERT INTO model_point (model_id, point_id) "
                "VALUES (:model_id, :point_id)"
            ),
            [{"model_id": model_id, "point_id": point_id} for model_id, point_id in bindings],
        )

    if legacy_sensor_points:
        rows = []
        for row in legacy_sensor_points:
            source = old_model_point_by_id[row["model_point_id"]]
            rows.append(
                {
                    "point_id": row["point_id"],
                    "sensor_id": row["sensor_id"],
                    "source_model_id": source["model_id"],
                    "source_point_id": canonical_by_old_id[row["model_point_id"]],
                    "point_name": row["point_name"],
                    "point_unit": _sensor_unit(row["point_unit"]),
                    "json_path": row["json_path"],
                }
            )
        bind.execute(
            sa.text(
                "INSERT INTO sensor_point "
                "(point_id, sensor_id, source_model_id, source_point_id, point_name, point_unit, json_path) "
                "VALUES (:point_id, :sensor_id, :source_model_id, :source_point_id, "
                ":point_name, :point_unit, :json_path)"
            ),
            rows,
        )

    migrated = list(
        bind.execute(
            sa.text(
                "SELECT point_id, sensor_id, point_name, point_unit, json_path "
                "FROM sensor_point ORDER BY point_id"
            )
        ).mappings()
    )
    before = [
        (
            r["point_id"],
            r["sensor_id"],
            r["point_name"],
            _sensor_unit(r["point_unit"]),
            r["json_path"],
        )
        for r in legacy_sensor_points
    ]
    after = [
        (r["point_id"], r["sensor_id"], r["point_name"], r["point_unit"], r["json_path"])
        for r in migrated
    ]
    if before != after:
        raise RuntimeError("sensor_point verification failed")

    op.drop_table("sensor_point_legacy")
    op.drop_table("model_point_legacy")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "sensor_model" in tables:
        return
    if not {"model", "point", "model_point", "sensor_point"}.issubset(tables):
        raise RuntimeError("normalized point schema is incomplete")

    bindings = list(
        bind.execute(
            sa.text(
                "SELECT mp.model_id, mp.point_id, p.point_name, p.point_unit "
                "FROM model_point mp JOIN point p ON p.point_id = mp.point_id "
                "ORDER BY mp.model_id, mp.point_id"
            )
        ).mappings()
    )
    binding_ids = {
        (row["model_id"], row["point_id"]): str(uuid4()) for row in bindings
    }
    sensor_points = list(
        bind.execute(sa.text("SELECT * FROM sensor_point ORDER BY point_id")).mappings()
    )

    op.rename_table("model_point", "model_point_normalized")
    op.rename_table("sensor_point", "sensor_point_normalized")
    _rename_postgresql_constraint(
        "model_point_normalized", "model_point_pkey", "model_point_normalized_pkey"
    )
    _rename_postgresql_constraint(
        "sensor_point_normalized", "sensor_point_pkey", "sensor_point_normalized_pkey"
    )
    op.create_table(
        "model_point",
        sa.Column("point_id", sa.String(100), primary_key=True),
        sa.Column("model_id", sa.String(100), nullable=True),
        sa.Column("point_name", sa.String(20), nullable=True),
        sa.Column("point_unit", sa.String(10), nullable=True),
        sa.Column("point_description", sa.String(200), nullable=True),
    )
    op.create_table(
        "sensor_point",
        sa.Column("point_id", sa.String(100), primary_key=True),
        sa.Column("sensor_id", sa.String(100), nullable=False),
        sa.Column("model_point_id", sa.String(100), nullable=True),
        sa.Column("point_name", sa.String(20), nullable=True),
        sa.Column("point_unit", sa.String(10), nullable=True),
        sa.Column("point_description", sa.String(200), nullable=True),
        sa.Column("json_path", sa.String(200), nullable=True),
    )
    op.create_index("ix_sensor_point_model_point_id", "sensor_point", ["model_point_id"])

    if bindings:
        bind.execute(
            sa.text(
                "INSERT INTO model_point "
                "(point_id, model_id, point_name, point_unit, point_description) "
                "VALUES (:legacy_id, :model_id, :point_name, :point_unit, NULL)"
            ),
            [dict(row, legacy_id=binding_ids[(row["model_id"], row["point_id"])]) for row in bindings],
        )
    if sensor_points:
        bind.execute(
            sa.text(
                "INSERT INTO sensor_point "
                "(point_id, sensor_id, model_point_id, point_name, point_unit, point_description, json_path) "
                "VALUES (:point_id, :sensor_id, :model_point_id, :point_name, :point_unit, NULL, :json_path)"
            ),
            [
                {
                    "point_id": row["point_id"],
                    "sensor_id": row["sensor_id"],
                    "model_point_id": binding_ids[(row["source_model_id"], row["source_point_id"])],
                    "point_name": row["point_name"],
                    "point_unit": row["point_unit"],
                    "json_path": row["json_path"],
                }
                for row in sensor_points
            ],
        )

    op.drop_table("sensor_point_normalized")
    op.drop_table("model_point_normalized")
    op.drop_table("point")
    op.rename_table("model", "sensor_model")
    _rename_postgresql_constraint("sensor_model", "model_pkey", "sensor_model_pkey")
