"""
CLI Commands for PlantDex
Supports both:
1. Standalone Python (zero dependencies): python cli.py backup-data
2. Flask Blueprint (on Render/server): flask cli backup-data
"""
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from config import Config
from database import init_db
from sync_worker import process_sync_queue


def do_init_db():
    print("Initializing PlantDex database...")
    init_db()
    print("Database initialization complete.")


def do_sync_pending(batch_size=10):
    print(f"Processing sync queue (batch size: {batch_size})...")
    synced = process_sync_queue(batch_size=batch_size)
    print(f"Sync complete. Successfully updated {synced} items.")


def do_backup_data(output_dir=None):
    dest_dir = Path(output_dir) if output_dir else Path(Config.DATA_DIR) / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_db_path = dest_dir / f"plantdex_backup_{timestamp}.db"

    db_src = Path(Config.DB_PATH)
    if db_src.exists():
        shutil.copy2(db_src, backup_db_path)
        print(f"Database backed up to: {backup_db_path}")
    else:
        print(f"Notice: Source database not found at {db_src}. Nothing to back up yet.")


def do_restore_data(backup_file):
    db_dest = Path(Config.DB_PATH)
    db_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, db_dest)
    print(f"Database restored from {backup_file} to {db_dest}")


# -------------------------------------------------------------
# Optional Flask Blueprint Registration (When Flask is installed on server)
# -------------------------------------------------------------
try:
    from flask import Blueprint
    import click

    cli_bp = Blueprint("cli", __name__)

    @cli_bp.cli.command("init-db")
    def init_db_command():
        do_init_db()

    @cli_bp.cli.command("sync-pending")
    @click.option("--batch-size", default=10, help="Number of pending items to sync.")
    def sync_pending_command(batch_size):
        do_sync_pending(batch_size)

    @cli_bp.cli.command("backup-data")
    @click.option("--output-dir", default=None, help="Directory to store backup.")
    def backup_data_command(output_dir):
        do_backup_data(output_dir)

    @cli_bp.cli.command("restore-data")
    @click.argument("backup_file", type=click.Path(exists=True))
    def restore_data_command(backup_file):
        do_restore_data(backup_file)

except ImportError:
    cli_bp = None


# -------------------------------------------------------------
# Standalone CLI Entry Point (Works with pure standard library Python!)
# -------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="PlantDex Standalone CLI Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init-db
    subparsers.add_parser("init-db", help="Initialize SQLite tables and baseline plants")

    # sync-pending
    sync_p = subparsers.add_parser("sync-pending", help="Run sync queue for pending details")
    sync_p.add_argument("--batch-size", type=int, default=10, help="Number of items to process")

    # backup-data
    bak_p = subparsers.add_parser("backup-data", help="Create timestamped database backup")
    bak_p.add_argument("--output-dir", default=None, help="Destination folder for backup")

    # restore-data
    res_p = subparsers.add_parser("restore-data", help="Restore database from backup file")
    res_p.add_argument("backup_file", help="Path to database backup file")

    args = parser.parse_args()

    if args.command == "init-db":
        do_init_db()
    elif args.command == "sync-pending":
        do_sync_pending(args.batch_size)
    elif args.command == "backup-data":
        do_backup_data(args.output_dir)
    elif args.command == "restore-data":
        do_restore_data(args.backup_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
