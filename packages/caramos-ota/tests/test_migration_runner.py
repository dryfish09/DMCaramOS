"""Tests for migration execution and release metadata recovery."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from caramos_ota_update.registry import MigrationDescriptor
from caramos_ota_update.runner import MigrationRunner


class MigrationRunnerTests(unittest.TestCase):
    def test_runs_bundled_timestamp_migration_and_finalizes_release(self) -> None:
        context = MagicMock()
        context.dry_run = False
        runner = MigrationRunner(context=context)
        legacy_ids = {f"v1_0_{version}" for version in range(2, 13)}
        ledger = {
            "schema": 1,
            "applied_migrations": [
                {"id": migration_id, "release": "1.0.12"}
                for migration_id in sorted(legacy_ids)
            ]
            + [
                {"id": "20260715090258_install_control_center"},
                {"id": "20260803120000_apply_three_dock_taskbar"},
                {"id": "20260804223346_change_default_wallpaper"},
                # Migration mới đã được applied, nên sẽ không chạy lại
                {"id": "20260827063012_update_zalo_hook"},
            ],
        }

        with (
            patch("caramos_ota_update.runner.bootstrap_ledger", return_value=ledger),
            patch("caramos_ota_update.runner.start_transaction", return_value="timestamp-batch") as start,
            patch("caramos_ota_update.runner.mark_transaction_success") as success,
            patch("caramos_ota_update.runner.mark_migration_running"),
            patch("caramos_ota_update.runner.mark_migration_complete"),
            patch("caramos_ota_update.runner.mark_applied"),
            patch.object(runner, "_run_one") as run_one,
        ):
            runner.run(current_version="1.0.15", target_version="1.0.16")

        # Cập nhật expected migration_ids để chỉ bao gồm migration chưa applied
        start.assert_called_once_with(
            target_version="1.0.16",
            migration_ids=["20260805111120_update_taskbar_pins_cleanup_desktop"],
        )
        run_one.assert_called_once()
        self.assertEqual(
            "20260805111120_update_taskbar_pins_cleanup_desktop",
            run_one.call_args.args[0].migration_id,
        )
        self.assertIsNone(run_one.call_args.args[0].release)
        context.update_release_file.assert_called_once_with("1.0.16")
        success.assert_called_once_with(
            transaction_id="timestamp-batch",
            installed_version="1.0.16",
        )

    def test_finalizes_release_when_target_migrations_are_already_applied(self) -> None:
        migration = MigrationDescriptor(
            migration_id="20260714090000_first_change",
            release=None,
            description="First change",
            source="test",
            directory=Path("/tmp/20260714090000_first_change"),
            module_path=Path("/tmp/20260714090000_first_change/migration.py"),
            schema=2,
            codename="noble",
            channel="stable",
            severity="normal",
            size="migration update",
            title="Update",
            summary="First change",
            release_notes_vi=[],
            release_notes_en=[],
        )
        ledger = {
            "schema": 1,
            "applied_migrations": [
                {"id": migration.migration_id},
            ],
        }
        context = MagicMock()
        context.dry_run = False
        runner = MigrationRunner(context=context)
        runner.discover = MagicMock(return_value=[migration])

        with (
            patch("caramos_ota_update.runner.bootstrap_ledger", return_value=ledger),
            patch("caramos_ota_update.runner.start_transaction", return_value="recovery") as start,
            patch("caramos_ota_update.runner.mark_transaction_success") as success,
        ):
            runner.run(current_version="1.0.2", target_version="1.0.3")

        start.assert_called_once_with(target_version="1.0.3", migration_ids=[])
        context.update_release_file.assert_called_once_with("1.0.3")
        success.assert_called_once_with(
            transaction_id="recovery",
            installed_version="1.0.3",
        )

    # Thêm test mới để kiểm tra migration Zalo
    def test_runs_zalo_migration_when_not_applied(self) -> None:
        """Test that Zalo migration runs when it hasn't been applied yet."""
        context = MagicMock()
        context.dry_run = False
        runner = MigrationRunner(context=context)
        legacy_ids = {f"v1_0_{version}" for version in range(2, 13)}
        ledger = {
            "schema": 1,
            "applied_migrations": [
                {"id": migration_id, "release": "1.0.12"}
                for migration_id in sorted(legacy_ids)
            ]
            + [
                {"id": "20260715090258_install_control_center"},
                {"id": "20260803120000_apply_three_dock_taskbar"},
                {"id": "20260804223346_change_default_wallpaper"},
                {"id": "20260805111120_update_taskbar_pins_cleanup_desktop"},
                # Zalo migration chưa được applied
            ],
        }

        with (
            patch("caramos_ota_update.runner.bootstrap_ledger", return_value=ledger),
            patch("caramos_ota_update.runner.start_transaction", return_value="zalo-batch") as start,
            patch("caramos_ota_update.runner.mark_transaction_success") as success,
            patch("caramos_ota_update.runner.mark_migration_running"),
            patch("caramos_ota_update.runner.mark_migration_complete"),
            patch("caramos_ota_update.runner.mark_applied"),
            patch.object(runner, "_run_one") as run_one,
        ):
            runner.run(current_version="1.0.16", target_version="1.0.17")

        start.assert_called_once_with(
            target_version="1.0.17",
            migration_ids=["20260827063012_update_zalo_hook"],
        )
        run_one.assert_called_once()
        self.assertEqual(
            "20260827063012_update_zalo_hook",
            run_one.call_args.args[0].migration_id,
        )
        self.assertIsNone(run_one.call_args.args[0].release)
        context.update_release_file.assert_called_once_with("1.0.17")
        success.assert_called_once_with(
            transaction_id="zalo-batch",
            installed_version="1.0.17",
        )

    def test_runs_both_pending_migrations_when_needed(self) -> None:
        """Test that both pending migrations run when needed."""
        context = MagicMock()
        context.dry_run = False
        runner = MigrationRunner(context=context)
        legacy_ids = {f"v1_0_{version}" for version in range(2, 13)}
        ledger = {
            "schema": 1,
            "applied_migrations": [
                {"id": migration_id, "release": "1.0.12"}
                for migration_id in sorted(legacy_ids)
            ]
            + [
                {"id": "20260715090258_install_control_center"},
                {"id": "20260803120000_apply_three_dock_taskbar"},
                {"id": "20260804223346_change_default_wallpaper"},
                # Cả 2 migration đều chưa applied
            ],
        }

        with (
            patch("caramos_ota_update.runner.bootstrap_ledger", return_value=ledger),
            patch("caramos_ota_update.runner.start_transaction", return_value="batch") as start,
            patch("caramos_ota_update.runner.mark_transaction_success") as success,
            patch("caramos_ota_update.runner.mark_migration_running"),
            patch("caramos_ota_update.runner.mark_migration_complete"),
            patch("caramos_ota_update.runner.mark_applied"),
            patch.object(runner, "_run_one") as run_one,
        ):
            runner.run(current_version="1.0.15", target_version="1.0.17")

        start.assert_called_once_with(
            target_version="1.0.17",
            migration_ids=[
                "20260805111120_update_taskbar_pins_cleanup_desktop",
                "20260827063012_update_zalo_hook",
            ],
        )
        # _run_one được gọi 2 lần
        self.assertEqual(2, run_one.call_count)
        
        # Kiểm tra migration đầu tiên
        first_call = run_one.call_args_list[0]
        self.assertEqual(
            "20260805111120_update_taskbar_pins_cleanup_desktop",
            first_call.args[0].migration_id,
        )
        
        # Kiểm tra migration thứ hai
        second_call = run_one.call_args_list[1]
        self.assertEqual(
            "20260827063012_update_zalo_hook",
            second_call.args[0].migration_id,
        )
        
        context.update_release_file.assert_called_once_with("1.0.17")
        success.assert_called_once_with(
            transaction_id="batch",
            installed_version="1.0.17",
        )


if __name__ == "__main__":
    unittest.main()
