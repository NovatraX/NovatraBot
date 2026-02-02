import discord
from discord import SlashCommandGroup
from discord.ext import commands, tasks

from .commands import AccountabilityCommands


class AccountabilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.commands = AccountabilityCommands(bot)
        self.db = self.commands.db
        self.helpers = self.commands.helpers
        self.reminder_task.start()

    log = SlashCommandGroup(name="log", description="Accountability Commands")

    @log.command(name="add", description="Log Your Daily Tasks")
    async def add(self, ctx: discord.ApplicationContext, task: str):
        await self.commands.add_command(ctx, task)

    @log.command(name="delete", description="Delete a logged task")
    async def log_delete(self, ctx: discord.ApplicationContext, task_number: int):
        await self.commands.delete_command(ctx, task_number)

    @log.command(name="stats", description="Get Your Accountability Stats")
    async def stats(
        self, ctx: discord.ApplicationContext, member: discord.Member = None
    ):
        await self.commands.stats_command(ctx, member)

    @log.command(name="history", description="Get Your Accountability History")
    async def history(self, ctx: discord.ApplicationContext):
        await self.commands.history_command(ctx)

    @log.command(name="leaderboard", description="Get Accountability Leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext):
        await self.commands.leaderboard_command(ctx)

    @log.command(name="weekly", description="Get Your Weekly Summary")
    async def weekly(self, ctx: discord.ApplicationContext):
        await self.commands.weekly_command(ctx)

    @log.command(name="set_target", description="Set your weekly task target")
    async def set_target(self, ctx: discord.ApplicationContext, target: int):
        await self.commands.set_weekly_target_command(ctx, target)

    reminder = log.create_subgroup(
        name="reminder", description="Daily reminder settings"
    )

    @reminder.command(name="set", description="Set a daily reminder to log your tasks")
    async def reminder_set(self, ctx: discord.ApplicationContext, time: str):
        await self.commands.set_reminder_command(ctx, time)

    @reminder.command(name="delete", description="Delete your daily task reminder")
    async def reminder_delete(self, ctx: discord.ApplicationContext):
        await self.commands.delete_reminder_command(ctx)

    @reminder.command(name="check", description="Check your current reminder settings")
    async def reminder_check(self, ctx: discord.ApplicationContext):
        await self.commands.check_reminder_command(ctx)

    store = log.create_subgroup(name="store", description="NovaCoins Store Commands")

    @store.command(name="view", description="View available items in the store")
    async def store_view(self, ctx: discord.ApplicationContext):
        await self.commands.store_command(ctx)

    @store.command(name="buy", description="Buy an item from the store")
    async def store_buy(self, ctx: discord.ApplicationContext, item_id: int):
        await self.commands.buy_item_command(ctx, item_id)

    @log.command(name="inventory", description="View your purchased items")
    async def inventory(self, ctx: discord.ApplicationContext):
        await self.commands.inventory_command(ctx)

    @log.command(name="use", description="Use an item from your inventory")
    async def use_item(self, ctx: discord.ApplicationContext, item_number: int):
        await self.commands.use_item_command(ctx, item_number)

    log_admin = log.create_subgroup(
        name="admin", description="Accountability Admin Commands"
    )

    @log_admin.command(name="reset", description="Reset Accountability Stats")
    async def reset(
        self, ctx: discord.ApplicationContext, member: discord.Member = None
    ):
        await self.commands.reset_command(ctx, member)

    @log_admin.command(name="add", description="Add NovaCoins And Streak To A User")
    async def add_currency(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        novacoins: int = 0,
        streak: int = 0,
    ):
        await self.commands.add_currency_command(ctx, member, novacoins, streak)

    @log_admin.command(
        name="remove", description="Remove NovaCoins And Streak From A User"
    )
    async def remove_currency(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        novacoins: int = 0,
        streak: int = 0,
    ):
        await self.commands.remove_currency_command(ctx, member, novacoins, streak)

    @log_admin.command(name="add_item", description="Add a new item to the store")
    async def add_store_item(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        price: int,
        description: str,
    ):
        await self.commands.add_item_command(ctx, name, price, description)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.commands.on_member_remove(member)

    @tasks.loop(minutes=1)
    async def reminder_task(self):
        await self.commands.send_reminders()

    @reminder_task.before_loop
    async def before_reminder_task(self):
        await self.bot.wait_until_ready()

    async def cog_load(self):
        await self.bot.wait_until_ready()
        await self.commands.cleanup_missing_users()

    def cog_unload(self):
        self.reminder_task.cancel()
        self.db.close()


def setup(bot: discord.Bot) -> None:
    bot.add_cog(AccountabilityCog(bot))
