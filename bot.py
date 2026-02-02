import datetime
import os
import traceback

import discord
import dotenv
from discord.ext import commands

dotenv.load_dotenv()
TOKEN = os.getenv("TOKEN")


intents = discord.Intents.all()
bot = discord.Bot(intents=intents, command_prefix="n!" or "nova!")


@bot.event
async def on_ready():
    print("--------------------------------")
    print("---- + LOADED NovatraBot + -----")
    print("--------------------------------")

    await bot.change_presence(
        activity=discord.Streaming(
            name="novatra.in",
            url="https://novatra.in",
        )
    )

    start_time = datetime.datetime.now()
    bot.start_time = start_time

    print("----- + LOADING COMMANDS + -----")
    print("--------------------------------")

    commands = 0

    for command in bot.walk_application_commands():
        commands += 1

        print(f"----- + Loaded : {command.name} ")

    print("--------------------------------")
    print(f"---- + Loaded : {commands}  Commands + -")
    print("--------------------------------")

    print("------- + LOADING COGS + -------")
    print(f"----- + Loaded : {len(bot.cogs)} Cogs + ------")
    print("--------------------------------")


@bot.slash_command(
    name="ping",
    description="Check Bot's Latency & Uptime",
    integration_types={
        discord.IntegrationType.guild_install,
    },
)
async def ping(ctx: discord.ApplicationContext):
    latency = bot.latency * 1000
    uptime = datetime.datetime.now() - bot.start_time

    uptime_seconds = uptime.total_seconds()
    uptime_str = str(datetime.timedelta(seconds=uptime_seconds)).split(".")[0]

    embed = discord.Embed(
        title=":ping_pong: _*Pong !*_",
        description=f"Uptime : {uptime_str}\nLatency : {latency:.2f} ms",
        color=0x2F3136,
    )

    await ctx.respond(embed=embed)


@bot.slash_command(
    name="info",
    description="Get Bot Information",
    integration_types={
        discord.IntegrationType.guild_install,
    },
)
async def info(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title=":information_source: Application Info",
        description="Official Bot For [ Novatra ](https://novatra.in)",
        color=0x2F3136,
    )

    embed.add_field(
        name="Links",
        value=":link: [ Terms ](https://novatra.in)\n:link: [ GitHub ](https://novatra.in)",
        inline=True,
    )

    embed.add_field(
        name="Developer",
        value=":gear: `Novatra`",
        inline=False,
    )

    embed.add_field(
        name="Created At",
        value=f":calendar: `{bot.user.created_at.strftime('%Y-%m-%d %H:%M:%S')}`",
        inline=True,
    )

    embed.set_thumbnail(url=bot.user.avatar.url)
    await ctx.respond(embed=embed)


@bot.slash_command(name="assests", description="Developer tool for assests")
async def assests(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title=":hammer: Developer Tool",
        description="Developer Tool For Assests",
        color=0x2F3136,
    )

    embed.add_field(
        name="<a:NovaCoins:1340334508838490223> NovaCoins",
        value="<a:NovaStreak:1340335713526222889> NovaStreak",
        inline=True,
    )

    await ctx.respond(embed=embed)


@bot.event
async def on_slash_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandOnCooldown):
        await ctx.respond(
            f":stopwatch: This Command Is On Cooldown. Try Again In {error.retry_after:.2f} Seconds"
        )
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.respond(":x: You Are Missing Required Arguments")
    elif isinstance(error, commands.errors.BadArgument):
        await ctx.respond(":x: Bad Argument Provided")
    elif isinstance(error, commands.errors.CommandInvokeError):
        await ctx.respond(":x: An Error Occurred While Executing The Command")
    elif isinstance(error, commands.errors.CommandNotFound):
        await ctx.respond(":x: Command Not Found")
    elif isinstance(error, commands.errors.CheckFailure):
        await ctx.respond(":x: You Do Not Have Permission To Use This Command")
    else:
        await ctx.respond(":x: An Error Occurred")


try:
    bot.load_extension("handlers.ai")
    bot.load_extension("handlers.help")
    bot.load_extension("handlers.links")
    bot.load_extension("utilities.status")
    bot.load_extension("handlers.reaction")
    bot.load_extension("utilities.feedback")
    bot.load_extension("utilities.accountability.accountability")
except Exception as e:
    print(f"Error Loading : {e}")
    traceback.print_exc()

bot.run(TOKEN)
