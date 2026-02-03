import datetime
import json
import os
import platform

import discord
import psutil
from discord.ext import commands, tasks

LINKS_JSON_PATH = "data/links.json"


class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_channel_id = None
        self.status_message = None
        self.update_status.start()

    def get_system_info(self):
        # Basic System Info
        system = platform.system()
        release = platform.release()

        # CPU Info
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()

        # Memory Info
        memory = psutil.virtual_memory()

        # Disk Info
        disk = psutil.disk_usage("/")

        # Boot Time
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time

        # Network Info
        net_io = psutil.net_io_counters()

        return {
            "system": system,
            "release": release,
            "cpu_usage": cpu_usage,
            "cpu_count": cpu_count,
            "cpu_freq": cpu_freq,
            "memory": memory,
            "disk": disk,
            "uptime": uptime,
            "net_io": net_io,
        }

    def format_bytes(self, bytes):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024
        return f"{bytes:.2f} PB"

    def create_progress_bar(self, percent, length=10):
        filled = int(percent / 100 * length)
        empty = length - filled

        if percent < 50:
            color = "🟩"
        elif percent < 80:
            color = "🟨"
        else:
            color = "🟥"

        return color * filled + "⬜" * empty

    def get_links_info(self):
        if not os.path.exists(LINKS_JSON_PATH):
            return {"exists": False}

        try:
            stat = os.stat(LINKS_JSON_PATH)
            with open(LINKS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            links = data.get("links", [])
            categories = {}
            for link in links:
                cat = link.get("category") or "uncategorized"
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "exists": True,
                "count": len(links),
                "size": stat.st_size,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime),
                "categories": categories,
            }
        except Exception:
            return {"exists": False}

    def get_services_info(self):
        return {
            "openrouter_model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            "openrouter_configured": bool(os.getenv("OPENROUTER_API_KEY")),
        }

    def get_github_sync_status(self):
        sync_cog = self.bot.get_cog("LinksSyncCog")
        if not sync_cog:
            return "⚠️ Not loaded"
        if sync_cog.last_push_time:
            timestamp = int(sync_cog.last_push_time.timestamp())
            return f"{'✅' if sync_cog.last_push_success else '❌'} <t:{timestamp}:f>"

        return "⏳ Pending"

    async def create_status_embed(self):
        info = self.get_system_info()

        if info["memory"].percent < 50:
            color = 0x2ECC71
        elif info["memory"].percent < 80:
            color = 0xF39C12
        else:
            color = 0xE74C3C

        embed = discord.Embed(
            title=f"📊 System Status | {info['system']} {info['release']}",
            color=color,
            timestamp=datetime.datetime.now(),
        )

        cpu_freq_current = info["cpu_freq"].current if info["cpu_freq"] else "N/A"
        cpu_bar = self.create_progress_bar(info["cpu_usage"])

        embed.add_field(
            name="🧠 CPU",
            value=(
                f"Usage : {cpu_bar} {info['cpu_usage']} %\n\n"
                f"**Cores** : {info['cpu_count']}\n"
                f"Frequency : {cpu_freq_current:.2f} MHz"
                if cpu_freq_current != "N/A"
                else "N/A"
            ),
            inline=False,
        )

        memory_bar = self.create_progress_bar(info["memory"].percent)
        embed.add_field(
            name="💾 Memory",
            value=f"**Usage** : {memory_bar} {info['memory'].percent} %\n\n"
            f"Total : {self.format_bytes(info['memory'].total)}\n"
            f"Available : {self.format_bytes(info['memory'].available)}",
            inline=False,
        )

        disk_bar = self.create_progress_bar(info["disk"].percent)
        embed.add_field(
            name="💿 Disk",
            value=f"**Usage** : {disk_bar} {info['disk'].percent} %\n\n"
            f"Total : {self.format_bytes(info['disk'].total)}\n"
            f"Free : {self.format_bytes(info['disk'].free)}",
            inline=False,
        )

        embed.add_field(
            name="🌐 Network",
            value=f"Sent : {self.format_bytes(info['net_io'].bytes_sent)}\n"
            f"Received : {self.format_bytes(info['net_io'].bytes_recv)}",
            inline=False,
        )

        links_info = self.get_links_info()
        services_info = self.get_services_info()
        sync_status = self.get_github_sync_status()

        if links_info.get("exists"):
            last_mod_ts = int(links_info["modified"].timestamp())

            embed.add_field(
                name="🔗 Links Database",
                value=f"**Total** : {links_info['count']} links\n"
                f"Modified : <t:{last_mod_ts}:f>\n"
                f"Sync : {sync_status}",
                inline=False,
            )
        else:
            embed.add_field(
                name="🔗 Links Database",
                value="❌ Not found",
                inline=False,
            )

        openrouter_status = (
            "✅ Configured" if services_info["openrouter_configured"] else "❌ Not set"
        )
        embed.add_field(
            name="⚙️ Services",
            value=f"**GitHub Sync** : {sync_status}"
            f"**OpenRouter** : {openrouter_status}\n\n"
            f"Model : `{services_info['openrouter_model']}`\n",
        )

        uptime = info["uptime"]
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        embed.set_footer(text=f"Uptime : {uptime_str} | Last updated")

        return embed

    @tasks.loop(minutes=5)
    async def update_status(self):
        if not self.status_channel_id:
            return

        channel = self.bot.get_channel(self.status_channel_id)
        if not channel:
            return

        embed = await self.create_status_embed()

        if self.status_message:
            try:
                await self.status_message.edit(embed=embed)
            except discord.NotFound:
                self.status_message = await channel.send(embed=embed)
        else:
            self.status_message = await channel.send(embed=embed)

    @update_status.before_loop
    async def before_update_status(self):
        await self.bot.wait_until_ready()

    @commands.slash_command(name="setstatus", description="Set Status Channel")
    @commands.has_permissions(administrator=True)
    async def set_status_channel(self, ctx):
        self.status_channel_id = ctx.channel.id
        await ctx.respond(
            "✅ This Channel Will Receive Status Messages Every 5 Minutes"
        )

        embed = await self.create_status_embed()
        self.status_message = await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(StatusCog(bot))
