import asyncio
import os
from pathlib import Path
from prism import cleanup_old_backups

async def test_cleanup():
    export_dir = Path("test_export")
    export_dir.mkdir(parents=True, exist_ok=True)
    project_uuid = "test-uuid"
    
    # Create some dummy backup files
    for i in range(10):
        timestamp = f"2026-05-16_00-00-{i:02d}"
        file_path = export_dir / f"project_{project_uuid}_{timestamp}.zip"
        file_path.write_text("dummy content")
        # Ensure different modification times
        os.utime(file_path, (1600000000 + i, 1600000000 + i))
    
    print(f"Created 10 dummy backups in {export_dir}")
    
    # Run cleanup with max_backups = 3
    await cleanup_old_backups(export_dir, project_uuid, 3)
    
    remaining_backups = list(export_dir.glob(f"project_{project_uuid}_*.zip"))
    print(f"Remaining backups: {len(remaining_backups)}")
    for f in sorted(remaining_backups):
        print(f"  {f.name}")
    
    if len(remaining_backups) == 3:
        print("✅ Cleanup test passed!")
    else:
        print("❌ Cleanup test failed!")
    
    # Cleanup test files
    for f in export_dir.glob("*"):
        f.unlink()
    export_dir.rmdir()

if __name__ == "__main__":
    asyncio.run(test_cleanup())
