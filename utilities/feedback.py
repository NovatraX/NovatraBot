import discord
import gspread
from discord.ext import commands
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("utilities/credentials.json", scope)

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
        
        self.add_item(discord.ui.InputText(label="Your Feedback", style=discord.InputTextStyle.long))
        self.add_item(discord.ui.InputText(label="Rating (1-5)", style=discord.InputTextStyle.short, placeholder="e.g., 5"))

    async def callback(self, interaction: discord.Interaction):
        feedback = self.children[0].value
        rating = self.children[1].value

        sheet.append_row([str(interaction.user), feedback, rating])

        await interaction.response.send_message("Thank you for your feedback!", ephemeral=True)

def setup(bot: discord.Bot) -> None:
    bot.add_cog(FeekbackCog(bot))
