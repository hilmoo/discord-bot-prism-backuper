import httpx
import aiofiles
from datetime import datetime
from pathlib import Path

async def cleanup_old_backups(export_dir: Path, project_uuid: str, max_backups: int):
    """Deletes old backups if the number of backups exceeds max_backups."""
    if max_backups <= 0:
        return

    backups = sorted(
        export_dir.glob(f"project_{project_uuid}_*.zip"),
        key=lambda x: x.stat().st_mtime
    )

    if len(backups) > max_backups:
        to_delete = backups[:len(backups) - max_backups]
        for f in to_delete:
            try:
                f.unlink()
                print(f"Deleted old backup: {f}")
            except Exception as e:
                print(f"Failed to delete old backup {f}: {e}")

async def export_prism_project(project_uuid: str, auth_token_0: str, auth_token_1: str, max_backups: int = 5) -> str:
    """
    Asynchronously sends a POST request to export a project from Prism and saves it as a ZIP file.

    Args:
        project_uuid (str): The UUID of the project to export.
        auth_token_0 (str): The value for the 'sb-api-auth-token.0' cookie.
        auth_token_1 (str): The value for the 'sb-api-auth-token.1' cookie.
        max_backups (int): Maximum number of backups to keep for this project.

    Returns:
        str: The path to the saved ZIP file.
    """
    url = f"https://prism.openai.com/api/projects/{project_uuid}/export"
    cookies = {
        "sb-api-auth-token.0": auth_token_0,
        "sb-api-auth-token.1": auth_token_1,
    }

    export_dir = Path("export")
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_path = export_dir / f"project_{project_uuid}_{timestamp}.zip"

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, cookies=cookies) as response:
            response.raise_for_status()

            async with aiofiles.open(file_path, "wb") as file:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await file.write(chunk)

    await cleanup_old_backups(export_dir, project_uuid, max_backups)

    return str(file_path)