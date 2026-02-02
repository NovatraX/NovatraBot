import discord
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.admin = [727012870683885578]

    @commands.slash_command(name="help", description="Sends Help Embed")
    async def help(self, ctx):
        embed = discord.Embed(
            title="Help", description="List Of Commands", color=0x2F3136
        )

        ping = self.bot.get_application_command("ping")
        info = self.bot.get_application_command("info")
        feedback = self.bot.get_application_command("feedback")

        embed.add_field(
            name=f"{ping.mention}", value="Sends Bot's Latency", inline=False
        )
        embed.add_field(
            name=f"{info.mention}",
            value="Sends Infromation About The Bot",
            inline=False,
        )
        embed.add_field(
            name=f"{feedback.mention}",
            value="Give Feedback About Bot And Website",
            inline=False,
        )

        await ctx.respond(embed=embed, view=CEmbed(self.bot))


class CEmbed(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.select(
        placeholder="Choose A Help Category",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="Accountability", description="Accountability Commands"
            ),
        ],
    )
    async def select_callback(self, select, interaction):
        # Main accountability commands embed
        AccountabilityEmbed = discord.Embed(
            title="Accountability Commands",
            description="List Of Accountability Commands",
            color=0x2F3136,
        )

        try:
            # Basic commands
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[0].mention}",
                value="Logs Your Completed Tasks For Daily Accountability",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[1].mention}",
                value="Deletes Your Tasks From Daily Accountability",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[2].mention}",
                value="Shows Your Daily Progress And Statistics",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[3].mention}",
                value="Shows Your Recent Task History",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[4].mention}",
                value="Shows The Leaderboard Of Most Accountable Users",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[5].mention}",
                value="Set Your Weekly Task Target",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[6].mention}",
                value="View Items You've Purchased From The Store",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name=f"{self.bot.get_application_command('log').subcommands[7].mention}",
                value="Use An Item From Your Inventory",
                inline=False,
            )
        except Exception as e:
            print(f"Exception : {e}")

            # Fallback in case subcommand indexing fails
            AccountabilityEmbed.add_field(
                name="/log add [task]",
                value="Logs Your Completed Tasks For Daily Accountability",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name="/log delete [task_number]",
                value="Deletes Your Tasks From Daily Accountability",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name="/log stats",
                value="Shows Your Daily Progress And Statistics",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name="/log history",
                value="Shows Your Recent Task History",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name="/log leaderboard",
                value="Shows The Leaderboard Of Most Accountable Users",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name="/log set_target [number]",
                value="Set Your Weekly Task Target",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name="/log inventory",
                value="View Items You've Purchased From The Store",
                inline=False,
            )
            AccountabilityEmbed.add_field(
                name="/log use [item_number]",
                value="Use An Item From Your Inventory",
                inline=False,
            )

        # Reminder commands embed
        ReminderEmbed = discord.Embed(
            title="Reminder Commands",
            description="Daily Task Logging Reminders",
            color=0xAAB99A,
        )

        ReminderEmbed.add_field(
            name="/log reminder set [HH:MM]",
            value="Set A Daily Reminder To Log Your Tasks (24-hour format)",
            inline=False,
        )
        ReminderEmbed.add_field(
            name="/log reminder delete",
            value="Delete Your Daily Task Reminder",
            inline=False,
        )
        ReminderEmbed.add_field(
            name="/log reminder check",
            value="Check Your Current Reminder Settings",
            inline=False,
        )

        # Store commands embed
        StoreEmbed = discord.Embed(
            title="Store Commands",
            description="NovaCoins Store",
            color=0xAAB99A,
        )

        StoreEmbed.add_field(
            name="/log store view",
            value="Browse Items Available In The Store",
            inline=False,
        )
        StoreEmbed.add_field(
            name="/log store buy [item_id]",
            value="Purchase An Item From The Store Using NovaCoins",
            inline=False,
        )

        # Admin Commands Embed
        AccountabilityEmbedAdmin = discord.Embed(
            title="Accountability Admin Commands",
            description="List Of Accountability Admin Commands",
            color=0x2F3136,
        )

        AccountabilityEmbedAdmin.add_field(
            name="/log admin reset",
            value="Reset User's Daily Accountability",
            inline=False,
        )
        AccountabilityEmbedAdmin.add_field(
            name="/log admin add",
            value="Add NovaCoins And Streak To A User",
            inline=False,
        )
        AccountabilityEmbedAdmin.add_field(
            name="/log admin remove",
            value="Remove NovaCoins And Streak From A User",
            inline=False,
        )
        AccountabilityEmbedAdmin.add_field(
            name="/log admin add_item",
            value="Add A New Item To The NovaCoins Store",
            inline=False,
        )

        if interaction.user.id in self.bot.get_cog("Help").admin:
            embeds = [
                AccountabilityEmbed,
                ReminderEmbed,
                StoreEmbed,
                AccountabilityEmbedAdmin,
            ]
        else:
            embeds = [AccountabilityEmbed, ReminderEmbed, StoreEmbed]

        if select.values[0] == "Accountability":
            await interaction.response.send_message(embeds=embeds, ephemeral=True)
        else:
            await interaction.response.send_message("Invalid Option")


def setup(bot):
    bot.add_cog(Help(bot))
