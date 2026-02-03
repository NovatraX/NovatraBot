import asyncio
import datetime
import hashlib
import os
import shutil
import subprocess

import discord
from discord.ext import commands, tasks

GITHUB_BRANCH = os.getenv("GITHUB_BRANCH")
GITHUB_CLONE_URL = os.getenv("GITHUB_CLONE_URL", "https://github.com/NovatraX/links")

GITHUB_SSH_DIR = os.getenv("GITHUB_SSH_DIR", "data/links")
GITHUB_FILE_PATH = os.getenv("GITHUB_FILE_PATH", "links.json")

GITHUB_SSH_KEY_PATH = os.getenv("GITHUB_SSH_KEY_PATH")

GIT_COMMIT_NAME = os.getenv("GIT_COMMIT_NAME", "SpreadSheets600")
GIT_COMMIT_EMAIL = os.getenv("GIT_COMMIT_EMAIL", "sohammaity239@gmail.com")
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

    def _run_git(self, args: list[str], cwd: str | None, env: dict) -> tuple[bool, str]:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            return False, output or "git command failed"
        return True, (result.stdout or "").strip()

    def _ensure_git_identity(self, env: dict) -> None:
        if "GIT_AUTHOR_NAME" not in env and "GIT_COMMITTER_NAME" not in env:
            env["GIT_AUTHOR_NAME"] = GIT_COMMIT_NAME or "SpreadSheets600"
            env["GIT_COMMITTER_NAME"] = GIT_COMMIT_NAME or "SpreadSheets600"

        if "GIT_AUTHOR_EMAIL" not in env and "GIT_COMMITTER_EMAIL" not in env:
            env["GIT_AUTHOR_EMAIL"] = GIT_COMMIT_EMAIL or "sohammaity239@gmail.com"
            env["GIT_COMMITTER_EMAIL"] = GIT_COMMIT_EMAIL or "sohammaity239@gmail.com"

    def _resolve_branch(self, repo_dir: str, env: dict, desired_branch: str | None):
        if desired_branch:
            return desired_branch
        ok, current = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], repo_dir, env
        )
        if ok and current and current != "HEAD":
            return current
        ok, origin_head = self._run_git(
            ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo_dir, env
        )
        if ok and origin_head:
            return origin_head.split("/", 1)[1] if "/" in origin_head else origin_head
        return None

    def _git_push_sync(self):
        if not shutil.which("git"):
            return False, "git is not installed on the host"

        if not os.path.exists(LINKS_JSON_PATH):
            return False, "links.json not found"

        env = os.environ.copy()
        self._ensure_git_identity(env)
        if GITHUB_SSH_KEY_PATH and "GIT_SSH_COMMAND" not in env:
            env["GIT_SSH_COMMAND"] = (
                f'ssh -i "{GITHUB_SSH_KEY_PATH}" -o IdentitiesOnly=yes '
                "-o StrictHostKeyChecking=accept-new"
            )

        repo_dir = GITHUB_SSH_DIR
        git_dir = os.path.join(repo_dir, ".git")
        desired_branch = GITHUB_BRANCH

        if not os.path.isdir(git_dir):
            os.makedirs(os.path.dirname(repo_dir) or ".", exist_ok=True)
            clone_args = ["clone"]
            if desired_branch:
                clone_args += ["--branch", desired_branch]
            clone_args += [GITHUB_CLONE_URL, repo_dir]
            ok, msg = self._run_git(clone_args, None, env)
            if not ok:
                return False, f"git clone failed: {msg}"

        ok, msg = self._run_git(["remote", "get-url", "origin"], repo_dir, env)
        if not ok:
            return False, f"git remote 'origin' not configured: {msg}"

        branch = self._resolve_branch(repo_dir, env, desired_branch)
        if desired_branch:
            ok, msg = self._run_git(["checkout", desired_branch], repo_dir, env)
            if not ok:
                ok, msg = self._run_git(
                    ["checkout", "-b", desired_branch, f"origin/{desired_branch}"],
                    repo_dir,
                    env,
                )
                if not ok:
                    return False, f"git checkout failed: {msg}"
            branch = desired_branch

        pull_args = (
            ["pull", "--rebase", "origin", branch] if branch else ["pull", "--rebase"]
        )
        ok, msg = self._run_git(pull_args, repo_dir, env)
        if not ok:
            return False, f"git pull failed: {msg}"

        target_path = os.path.join(repo_dir, GITHUB_FILE_PATH)
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(LINKS_JSON_PATH, "rb") as source:
            content = source.read()
        with open(target_path, "wb") as dest:
            dest.write(content)

        ok, msg = self._run_git(["add", GITHUB_FILE_PATH], repo_dir, env)
        if not ok:
            return False, f"git add failed: {msg}"

        ok, _ = self._run_git(["diff", "--cached", "--quiet"], repo_dir, env)
        if ok:
            return True, "No changes to push"

        ok, msg = self._run_git(
            ["commit", "-m", "chore: update links.json"], repo_dir, env
        )
        if not ok:
            return False, f"git commit failed: {msg}"

        push_args = (
            ["push", "--force", "origin", branch]
            if branch
            else ["push", "--force", "origin", "HEAD"]
        )
        ok, msg = self._run_git(push_args, repo_dir, env)
        if not ok:
            return False, f"git push failed: {msg}"

        return True, "Success"

    async def _git_push(self) -> tuple[bool, str]:
        return await asyncio.to_thread(self._git_push_sync)

    async def _sync_once(self, force: bool = False) -> None:
        current_hash = self._get_file_hash()
        if current_hash is None:
            return

        if not force and self._last_hash == current_hash:
            return

        pushed, msg = await self._git_push()
        self.last_sync_time = datetime.datetime.now()
        self.last_push_time = datetime.datetime.now()
        self.last_push_success = pushed

        if pushed or msg == "No changes to push":
            self._last_hash = current_hash

        if pushed:
            print("[LinkSync] Pushed updated links.json to GitHub")
        else:
            print(f"[LinkSync] Push failed: {msg}")

    @tasks.loop(seconds=30)
    async def sync_links(self):
        await self._sync_once()

    @sync_links.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()
        await self._sync_once(force=True)

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

        pushed, msg = await self._git_push()
        self.last_sync_time = datetime.datetime.now()
        self.last_push_time = datetime.datetime.now()
        self.last_push_success = pushed
        if pushed or msg == "No changes to push":
            self._last_hash = current_hash

        if pushed:
            await ctx.followup.send("✅ Successfully pushed links.json to GitHub")
        else:
            await ctx.followup.send(f"❌ {msg}")


def setup(bot: discord.Bot):
    bot.add_cog(LinksSyncCog(bot))
