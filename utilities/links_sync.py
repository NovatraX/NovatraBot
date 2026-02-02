import datetime
import hashlib
import os
import subprocess

import discord
from discord.ext import commands, tasks

LINKS_JSON_PATH = "data/links.json"


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

    def _git_push(self) -> tuple[bool, str]:
        github_pat = os.getenv("GITHUB_PAT")
        if not github_pat:
            return False, "GITHUB_PAT not set"

        try:
            subprocess.run(
                ["git", "add", LINKS_JSON_PATH],
                cwd=os.getcwd(),
                check=True,
                capture_output=True,
            )

            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
            )
            if LINKS_JSON_PATH not in diff_result.stdout:
                return False, "No changes staged"

            subprocess.run(
                ["git", "commit", "-m", "chore: update links.json"],
                cwd=os.getcwd(),
                check=True,
                capture_output=True,
            )

            remote_url = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
            ).stdout.strip()

            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_ASKPASS"] = ""
            env["GIT_CREDENTIAL_HELPER"] = ""

            if remote_url.startswith("https://"):
                parts = remote_url.replace("https://", "").split("/")
                repo_path = "/".join(parts[-2:]) if len(parts) >= 2 else remote_url
                auth_url = f"https://x-access-token:{github_pat}@github.com/{repo_path}"

                result = subprocess.run(
                    ["git", "push", auth_url, "HEAD"],
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                if result.returncode != 0:
                    return False, f"Push failed: {result.stderr}"
            else:
                result = subprocess.run(
                    ["git", "push"],
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                if result.returncode != 0:
                    return False, f"Push failed: {result.stderr}"

            return True, "Success"
        except subprocess.CalledProcessError as e:
            return False, f"Git error: {e.stderr.decode() if e.stderr else str(e)}"

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
            pushed, msg = self._git_push()
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

        pushed, msg = self._git_push()
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
