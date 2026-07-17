import os
import shutil
from ..config import load_config
from ..utils.printer import print_info, print_error, print_success, print_warning
from ..utils.confirm import confirm_action

def run_rollback(timestamp: str):
    config = load_config()
    doc_dir = config.project_doc_dir
    snapshots_dir = os.path.join(doc_dir, "snapshots")
    
    if not os.path.exists(snapshots_dir):
        print_error("No snapshots found to roll back.")
        return

    snapshots = sorted(os.listdir(snapshots_dir))
    if not snapshots:
        print_error("No snapshots found to roll back.")
        return

    selected_snapshot = timestamp
    if not selected_snapshot:
        print_info("Available snapshots:")
        for idx, snap in enumerate(snapshots, 1):
            print_info(f"  [{idx}] {snap}")
        
        # Simple selection index
        import click
        choice = click.prompt("Select a snapshot to roll back to (index)", type=int)
        if 1 <= choice <= len(snapshots):
            selected_snapshot = snapshots[choice - 1]
        else:
            print_error("Invalid selection.")
            return

    target_snap_dir = os.path.join(snapshots_dir, selected_snapshot)
    if not os.path.exists(target_snap_dir):
        print_error(f"Snapshot directory {selected_snapshot} not found.")
        return

    print_warning(f"This will revert the active files in the directory back to snapshot: {selected_snapshot}")
    if not confirm_action("Are you sure you want to proceed?"):
        print_info("Rollback cancelled.")
        return

    # Apply restore
    for root, dirs, files in os.walk(target_snap_dir):
        for file in files:
            snap_file_path = os.path.join(root, file)
            rel_path = os.path.relpath(snap_file_path, target_snap_dir)
            dest_path = os.path.join(".", rel_path)
            
            # Ensure folder exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            try:
                shutil.copy2(snap_file_path, dest_path)
                print_info(f"Restored: {rel_path}")
            except Exception as e:
                print_error(f"Failed to restore {rel_path}: {e}")

    # Re-run status check to sync doc indices
    print_info("Running status sync...")
    from .update import run_update
    run_update([], True, False) # Run dirty update to sync docs
    print_success("Rollback complete.")
