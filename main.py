import os
import asyncio
import discord
from discord.ext import tasks, commands
from discord.ui import Modal, TextInput, View, Button
from dotenv import load_dotenv
from datetime import time
from prism import export_prism_project

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAX_BACKUPS = os.getenv("MAX_BACKUPS", "5")
_channel_id = os.getenv("CHANNEL_ID")
_user_id = os.getenv("USER_ID")

CHANNEL_ID = int(_channel_id) if _channel_id and _channel_id.isdigit() else None
USER_ID = int(_user_id) if _user_id and _user_id.isdigit() else None


class ConfigModal(Modal, title="Prism Backup Configuration"):
    """Modal to collect project UUID and auth tokens."""

    project_uuid = TextInput(
        label="Project UUID",
        style=discord.TextStyle.short,
        placeholder="Enter your Project UUID",
        required=True,
    )

    token_0 = TextInput(
        label="sb-api-auth-token.0",
        style=discord.TextStyle.short,
        placeholder="Enter auth token 0",
        required=True,
    )

    token_1 = TextInput(
        label="sb-api-auth-token.1",
        style=discord.TextStyle.short,
        placeholder="Enter auth token 1",
        required=True,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # Acknowledge the modal submission immediately to prevent timeout
        await interaction.response.send_message(
            "Verifying parameters with an immediate export..."
        )

        try:
            # Extract values from the modal
            uuid = self.project_uuid.value.strip()
            t0 = self.token_0.value.strip()
            t1 = self.token_1.value.strip()

            file_path = await export_prism_project(uuid, t0, t1)

            # Save to bot state
            self.bot.project_uuid = uuid
            self.bot.auth_token_0 = t0
            self.bot.auth_token_1 = t1
            self.bot.is_configured = True

            success_msg = (
                f"✅ Verification successful! Backup saved to: `{file_path}`\n"
                "The hourly backup task is now active."
            )
            await interaction.edit_original_response(content=success_msg)

        except Exception as e:
            error_msg = f"❌ Verification failed: {str(e)}\nPlease click the button to try again."
            await interaction.edit_original_response(content=error_msg)
            # Since configuration failed, we trigger the config flow again
            channel = self.bot.get_channel(CHANNEL_ID)
            if channel:
                await self.bot.initiate_configuration(channel)


class ConfigView(View):
    """View containing the button to trigger the ConfigModal."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Configure Backup",
        style=discord.ButtonStyle.primary,
        custom_id="config_backup_btn",
        emoji="⚙️",
    )
    async def configure_button(self, interaction: discord.Interaction, button: Button):
        # Ensure only the authorized user can open the modal
        if interaction.user.id != USER_ID:
            await interaction.response.send_message(
                "You are not authorized to configure this bot.", ephemeral=True
            )
            return

        modal = ConfigModal(self.bot)
        await interaction.response.send_modal(modal)


class PrismBackuperBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.project_uuid = None
        self.auth_token_0 = None
        self.auth_token_1 = None
        self.is_configured = False
        self.config_lock = asyncio.Lock()

    async def setup_hook(self):
        # Register the persistent view so the button works after restarts
        self.add_view(ConfigView(self))

        # Start the hourly task loop (running every hour at minute 00)
        hourly_times = [time(hour=h, minute=0) for h in range(24)]
        self.backup_loop.change_interval(time=hourly_times)
        self.backup_loop.start()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        channel = self.get_channel(CHANNEL_ID)
        if channel:
            if not self.is_configured:
                await self.initiate_configuration(channel)
        else:
            print(f"Error: Could not find channel with ID {CHANNEL_ID}")

    async def initiate_configuration(self, channel, error_msg=None):
        async with self.config_lock:
            if error_msg:
                await channel.send(f"<@{USER_ID}> {error_msg}")

            view = ConfigView(self)
            await channel.send(
                f"<@{USER_ID}> The bot requires configuration to proceed. Click the button below to enter your credentials.",
                view=view,
            )

    @tasks.loop()
    async def backup_loop(self):
        if not self.is_configured:
            return

        print(f"Running scheduled backup at {discord.utils.utcnow()}")
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"Error: Could not find channel with ID {CHANNEL_ID}")
            return

        try:
            file_path = await export_prism_project(
                self.project_uuid, self.auth_token_0, self.auth_token_1, MAX_BACKUPS
            )
            await channel.send(
                f"📦 Successfully backed up project `{self.project_uuid}`.\nFile: `{file_path}`"
            )
        except Exception as e:
            self.is_configured = False
            await self.initiate_configuration(
                channel, f"Error during scheduled backup: {str(e)}"
            )

    @backup_loop.before_loop
    async def before_backup_loop(self):
        await self.wait_until_ready()


if __name__ == "__main__":
    if not DISCORD_TOKEN or not CHANNEL_ID or not USER_ID:
        print(
            "Error: DISCORD_TOKEN, CHANNEL_ID, and USER_ID must be set in environment variables."
        )
    else:
        bot = PrismBackuperBot()
        bot.run(DISCORD_TOKEN)
