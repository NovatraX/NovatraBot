import discord
import gspread
from discord.ext import commands
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

client = gspread.authorize(creds)
sheet = client.open("Novatra Feedback").sheet1

print("-- + Google Sheets Loaded + ----")


class FeekbackCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @commands.slash_command(name="feedback", description="⭐ Submit Your Feedback")
    async def feedback(self, ctx: discord.ApplicationContext):
        await ctx.send_modal(FeedbackModal())


class FeedbackModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="User Feedback")

        self.add_item(
            discord.ui.InputText(
                label="How was your overall experience ?",
                style=discord.InputTextStyle.short,
                placeholder="⭐ Rating : 1 - 10",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Would you recommend this app to others ?",
                style=discord.InputTextStyle.short,
                placeholder="Yes / No / Maybe",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Any issues while using the app ?",
                style=discord.InputTextStyle.long,
                placeholder="Write about the issues you faced while using the app ! ",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Any suggestions for improvement ?",
                style=discord.InputTextStyle.long,
                placeholder="Write your suggestions that we can use to improve the app !",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        experience = self.children[0].value
        would_recommend = self.children[1].value
        issues = self.children[2].value
        suggestions = self.children[3].value

        sheet.append_row(
            [
                str(interaction.user),
                str(interaction.user.id),
                experience,
                would_recommend,
                issues,
                suggestions,
            ]
        )

        print("-- + Feedback Submitted + ------")

        embed_user = discord.Embed(
            title="Feedback Submitted Successfully",
            description="Thank you for submitting your feedback !",
            color=discord.Color.green(),
        )
        embed_admin = discord.Embed(
            title="New Feedback Received",
            color=discord.Color.green(),
        )

        embed_admin.add_field(name="User", value=str(interaction.user))
        embed_admin.add_field(name="User ID", value=f"<@{str(interaction.user.id)}")
        embed_admin.add_field(name="Experience", value=experience)
        embed_admin.add_field(name="Reccomend ?", value=would_recommend, inline=False)
        embed_admin.add_field(name="Suggestions", value=suggestions, inline=False)
        embed_admin.add_field(name="Issues", value=issues, inline=False)

        embed_admin.set_footer(
            text="Feedback Received",
            icon_url=interaction.user.avatar,
        )

        await interaction.response.send_message(embed=embed_user, ephemeral=True)

        channel = interaction.guild.get_channel(1340318888143093836)
        await channel.send(embed=embed_admin)


def setup(bot: discord.Bot) -> None:
    bot.add_cog(FeekbackCog(bot))
