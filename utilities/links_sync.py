import datetime
import hashlib
import os
import shutil
import subprocess

import discord
from discord.ext import commands, tasks

LINKS_JSON_PATH = "data/links.json"
LINKS_REPO_DIR = "data/links-repo"
LINKS_REPO_URL = "github.com/NovatraX/links.git"


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

    def _ensure_repo(self, github_pat: str) -> tuple[bool, str]:
        auth_url = f"https://x-access-token:{github_pat}@{LINKS_REPO_URL}"
        env = self._git_env()

        if os.path.exists(LINKS_REPO_DIR):
            result = subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=LINKS_REPO_DIR,
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                shutil.rmtree(LINKS_REPO_DIR, ignore_errors=True)
            else:
                return True, "Repo updated"

        os.makedirs(os.path.dirname(LINKS_REPO_DIR), exist_ok=True)
        result = subprocess.run(
            ["git", "clone", auth_url, LINKS_REPO_DIR],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            return False, f"Clone failed: {result.stderr}"
        return True, "Repo cloned"

    def _git_env(self) -> dict:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = ""
        env["GIT_CREDENTIAL_HELPER"] = ""
        return env

    def _git_push(self) -> tuple[bool, str]:
        github_pat = os.getenv("GITHUB_PAT")
        if not github_pat:
            return False, "GITHUB_PAT not set"

        ok, msg = self._ensure_repo(github_pat)
        if not ok:
            return False, msg

        shutil.copy(LINKS_JSON_PATH, os.path.join(LINKS_REPO_DIR, "links.json"))

        env = self._git_env()

        try:
            subprocess.run(
                ["git", "add", "links.json"],
                cwd=LINKS_REPO_DIR,
                check=True,
                capture_output=True,
            )

            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=LINKS_REPO_DIR,
                capture_output=True,
                text=True,
            )
            if "links.json" not in diff_result.stdout:
                return False, "No changes to push"

            subprocess.run(
                ["git", "commit", "-m", "chore: update links.json"],
                cwd=LINKS_REPO_DIR,
                check=True,
                capture_output=True,
            )

            auth_url = f"https://x-access-token:{github_pat}@{LINKS_REPO_URL}"
            result = subprocess.run(
                ["git", "push", auth_url, "HEAD"],
                cwd=LINKS_REPO_DIR,
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
