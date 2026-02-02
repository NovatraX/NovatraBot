import base64
import datetime
import hashlib
import os

import aiohttp
import discord
from discord.ext import commands, tasks

GITHUB_REPO = "links"
GITHUB_OWNER = "NovatraX"
GITHUB_FILE_PATH = "links.json"
LINKS_JSON_PATH = "data/links.json"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"


class LinksSyncCog(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self._last_hash: str | None = None
        self.last_sync_time: datetime.datetime | None = None
        self.last_push_time: datetime.datetime | None = None
        self.last_push_success: bool | None = None
        self.sync_links.start()

    def cog_unload(self):
        self.sync_links.cancel()

    def _get_file_hash(self) -> str | None:
        if not os.path.exists(LINKS_JSON_PATH):
            return None
        with open(LINKS_JSON_PATH, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    async def _get_remote_sha(
        self, session: aiohttp.ClientSession, headers: dict
    ) -> str | None:
        try:
            async with session.get(GITHUB_API_URL, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("sha")
                return None
        except aiohttp.ClientError:
            return None

    async def _github_push(self) -> tuple[bool, str]:
        github_pat = os.getenv("GITHUB_PAT")
        if not github_pat:
            return False, "GITHUB_PAT not set"

        if not os.path.exists(LINKS_JSON_PATH):
            return False, "links.json not found"

        with open(LINKS_JSON_PATH, "rb") as f:
            content = f.read()

        encoded_content = base64.b64encode(content).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {github_pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with aiohttp.ClientSession() as session:
            remote_sha = await self._get_remote_sha(session, headers)

            payload: dict = {
                "message": "chore: update links.json",
                "content": encoded_content,
            }
            if remote_sha:
                payload["sha"] = remote_sha

            try:
                async with session.put(
                    GITHUB_API_URL, headers=headers, json=payload
                ) as resp:
                    if resp.status in (200, 201):
                        return True, "Success"
                    error_data = await resp.json()
                    error_msg = error_data.get("message", "Unknown error")
                    return False, f"Push failed: {error_msg}"
            except aiohttp.ClientError as e:
                return False, f"Request failed: {e}"

    @tasks.loop(minutes=30)
    async def sync_links(self):
        self.last_sync_time = datetime.datetime.now()
        current_hash = self._get_file_hash()
        if current_hash is None:
            return

        if self._last_hash is None:
            self._last_hash = current_hash
            return

        if current_hash != self._last_hash:
            pushed, msg = await self._github_push()
            self.last_push_time = datetime.datetime.now()
            self.last_push_success = pushed
            if pushed:
                print("[LinkSync] Pushed updated links.json to GitHub")
            else:
                print(f"[LinkSync] Push failed: {msg}")
            self._last_hash = current_hash

    @sync_links.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()

    @commands.slash_command(
        name="synclinks", description="Manually sync links.json to GitHub"
    )
    @commands.has_permissions(administrator=True)
    async def sync_now(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        current_hash = self._get_file_hash()
        if current_hash is None:
            await ctx.followup.send("❌ links.json not found")
            return

        pushed, msg = await self._github_push()
        self.last_sync_time = datetime.datetime.now()
        self.last_push_time = datetime.datetime.now()
        self.last_push_success = pushed
        self._last_hash = current_hash

        if pushed:
            await ctx.followup.send("✅ Successfully pushed links.json to GitHub")
        else:
            await ctx.followup.send(f"❌ {msg}")


def setup(bot: discord.Bot):
    bot.add_cog(LinksSyncCog(bot))
