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

        await ctx.respond(embeds=embed, view=CEmbed(self.bot))


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
        AccountabilityEmbed = discord.Embed(
            title="Accountability Commands",
            description="List Of Accountability Commands",
            color=0x2F3136,
        )

        AccountabilityEmbed.add_field(
            name=f"{self.bot.get_application_command('log').subcommands[0].mention}",
            value="Logs Your Tasks For Daily Accountability",
            inline=False,
        )

        AccountabilityEmbed.add_field(
            name=f"{self.bot.get_application_command('log').subcommands[2].mention}",
            value="Tells About Your Daily Progress And Statistics",
            inline=False,
        )

        AccountabilityEmbed.add_field(
            name=f"{self.bot.get_application_command('log').subcommands[1].mention}",
            value="Deletes Your Tasks From Daily Accountability",
            inline=False,
        )

        AccountabilityEmbed.add_field(
            name=f"{self.bot.get_application_command('log').subcommands[3].mention}",
            value="Shows The Leaderboard Of Most Accountable Users",
            inline=False,
        )

        AccountabilityEmbedAmin = discord.Embed(
            title="Accountability Admin Commands",
            description="List Of Accountability Admin Commands",
            color=0x2F3136,
        )

        AccountabilityEmbedAmin.add_field(
            name="/log admin reset",
            value="Reset User's Daily Accountability",
            inline=False,
        )

        AccountabilityEmbedAmin.add_field(
            name="/log admin add_novacoins",
            value="Add Novacoins To User's Account",
            inline=False,
        )

        AccountabilityEmbedAmin.add_field(
            name="/log admin remove_novacoins",
            value="Remove Novacoins To User's Account",
            inline=False,
        )

        AccountabilityEmbedAmin.add_field(
            name="/log admin add_streak",
            value="Add Streak To User's Account",
            inline=False,
        )

        AccountabilityEmbedAmin.add_field(
            name="/log admin remove_streak",
            value="Add Streak To User's Account",
            inline=False,
        )

        if interaction.user.id in self.bot.get_cog("Help").admin:
            embeds = [AccountabilityEmbed, AccountabilityEmbedAmin]

        else:
            embeds = [AccountabilityEmbed]

        if select.values[0] == "Accountability":
            await interaction.response.send_message(embeds=embeds, ephemeral=True)
        else:
            await interaction.response.send_message("Invalid Option")


def setup(bot):
    bot.add_cog(Help(bot))
