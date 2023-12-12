import discord
from discord.ext import commands
import json
import os

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# File to store user data
user_data_file = 'user_data.json'

# Load user data if file exists
if os.path.isfile(user_data_file):
    with open(user_data_file, 'r') as file:
        user_xp = json.load(file)
else:
    user_xp = {}

# Ranks and their XP thresholds
ranks = {
    'Bronze': {'color': 0xa52a2a, 'xp': 0},
    'Silver': {'color': 0xc0c0c0, 'xp': 100},
    'Gold': {'color': 0xffd700, 'xp': 200},
    'Diamond': {'color': 0x0d98ba, 'xp': 300},
    'Platinum': {'color': 0x0b5394, 'xp': 400}
}

def get_rank(xp):
    for rank, details in reversed(ranks.items()):
        if xp >= details['xp']:
            return rank, details['color']
    return 'Unranked', 0xffffff

# Function to save user data
def save_user_data():
    with open(user_data_file, 'w') as file:
        json.dump(user_xp, file, indent=4)

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Update user data
    user_id = str(message.author.id)  # JSON keys must be strings
    if user_id not in user_xp:
        user_xp[user_id] = {'xp': 0, 'messages': 0, 'last_message_time': '', 'last_message': ''}

    xp_gain = 5 + (10 if len(message.attachments) > 0 else 0)
    user_xp[user_id]['xp'] += xp_gain
    user_xp[user_id]['messages'] += 1
    user_xp[user_id]['last_message_time'] = str(message.created_at)
    user_xp[user_id]['last_message'] = str(message.content)

    save_user_data()  # Save data after each message
    await bot.process_commands(message)

@bot.command(name='xp')
async def xp(ctx):
    user_id = str(ctx.author.id)
    user_info = user_xp.get(user_id, {'xp': 0, 'messages': 0, 'last_message_time': ''})
    xp = user_info['xp']
    rank, color = get_rank(xp)

    # URLs of the rank logos
    rank_logos = {
        'Bronze': 'https://imgur.com/HTPfGgO',
        'Silver': 'https://imgur.com/LTty75m',
        'Gold': 'https://imgur.com/QxNWnJC',
        'Diamond': 'https://imgur.com/NKasw3P',
        'Platinum': 'https://imgur.com/XJzFSJP'
    }

    logo_url = rank_logos.get(rank, 'https://imgur.com/HTPfGgO')
    embed = discord.Embed(title=f"{ctx.author.display_name}'s Rank", description=f"Rank: {rank}\nXP: {xp}", color=color)
    embed.set_thumbnail(url=logo_url)
    await ctx.send(embed=embed)

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear(ctx):
    user_id = str(ctx.author.id)  # Convert user ID to string
    user_info = user_xp.get(user_id, {'xp': 0, 'messages': 0, 'last_message_time': ''})
    xp = user_info['xp']
    rank, _ = get_rank(xp)

    if rank in ['Silver', 'Gold', 'Diamond', 'Platinum']:
        deleted = await ctx.channel.purge(limit=20)
        await ctx.send(f'Deleted {len(deleted)} message(s)', delete_after=5)
    else:
        await ctx.send('You need to be at least Silver rank to use this command.', delete_after=5)

# Queue to store user IDs
queue = []

@bot.command(name='queue')
async def queue_command(ctx, *, arg):
    global queue
    if arg == "join":
        # Check if user is in the Lobby voice channel
        if ctx.author.voice and ctx.author.voice.channel.name == 'Lobby':
            if ctx.author.id not in queue:
                queue.append(ctx.author.id)
                await ctx.send(f'{ctx.author.display_name} joined the queue.')
            else:
                await ctx.send('You are already in the queue.')

            # Check if queue is full
            if len(queue) == 8:
                await split_teams(ctx)
        else:
            await ctx.send('You must be in a Lobby voice channel to join the queue.')

    elif arg == "info":
        if queue:
            users = []
            for user_id in queue:
                member = ctx.guild.get_member(user_id)
                if member:
                    users.append(member.mention)
                else:
                    users.append(f'Unknown Member (ID: {user_id})')
            await ctx.send(f'Queue: {len(queue)}/8: ' + ', '.join(users))
        else:
            await ctx.send('The queue is currently empty.')

    elif arg == "leave":
        if ctx.author.id in queue:
            queue.remove(ctx.author.id)
            await ctx.send(f'You have left the queue, {ctx.author.display_name}.')
        else:
            await ctx.send(f'You are not in the queue, {ctx.author.display_name}.')

    elif arg == "disband":
        # Check if the user has the 'Founder' or 'Admin' role
        if any(role.name in ['Founder', 'Admin'] for role in ctx.author.roles):
            queue.clear()
            await ctx.send('The queue has been disbanded.')
        else:
            await ctx.send('You do not have permission to disband the queue.')

async def split_teams(ctx):
    global queue
    team_a = queue[:4]
    team_b = queue[4:]

    # Move users to respective voice channels
    for user_id in team_a:
        member = ctx.guild.get_member(user_id)
        team_a_channel = get(ctx.guild.voice_channels, name='Team A')
        await member.move_to(team_a_channel)

    for user_id in team_b:
        member = ctx.guild.get_member(user_id)
        team_b_channel = get(ctx.guild.voice_channels, name='Team B')
        await member.move_to(team_b_channel)

    await ctx.send('Teams are ready and users have been moved to their respective channels.')

    queue = []  # Clear the queue after splitting teams

@bot.event
async def on_voice_state_update(member, before, after):
    global queue
    # Check if the member was in the Lobby channel and now is not
    if before.channel and before.channel.name == 'Lobby' and (not after.channel or after.channel.name != 'Lobby'):
        if member.id in queue:
            queue.remove(member.id)
            await before.channel.send(f'{member.display_name} has left the Lobby and has been removed from the queue.')

# Replace 'YOUR_BOT_TOKEN' with your bot's token
bot.run('MTE3OTA0OTY3NjI3Njc3Njk4MA.GZeIe2.1hCgMiF_-ng_K3Eeu5Pg9FfJNatvGJfA_hVryY')
