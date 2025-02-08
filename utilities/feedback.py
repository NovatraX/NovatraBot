import discord
import gspread
from discord.ext import commands
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "utilities/credentials.json", scope
)

client = gspread.authorize(creds)
sheet = client.open("Novatra Feedback").sheet1

print("-- + Google Sheets Loaded + ----")


class FeekbackCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @commands.slash_command(name="feedback", description="Submit your feedback")
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
                label="Did you face any issues while using the app ?",
                style=discord.InputTextStyle.long,
                placeholder="Write about the issues you faced",
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Any suggestions for improvement ?",
                style=discord.InputTextStyle.long,
                placeholder="Write your suggestions",
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

        await interaction.response.send_message(
            "Thank You For Your Valuable Feedback", ephemeral=True
        )


def setup(bot: discord.Bot) -> None:
    bot.add_cog(FeekbackCog(bot))
