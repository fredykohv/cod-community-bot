import discord
from discord.ext import commands
import json
import os
import queue_system

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

user_data_file = 'user_data.json'

if os.path.isfile(user_data_file):
	with open(user_data_file, 'r') as file:
		user_xp = json.load(file)
else:
	user_xp = {}

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

def save_user_data():
	with open(user_data_file, 'w') as file:
		json.dump(user_xp, file, indent=4)

@bot.event
async def on_ready():
	print(f'{bot.user.name} has connected to Discord!')
	await queue_system.setup(bot)

@bot.event
async def on_message(message):
	if message.author == bot.user:
		return

	user_id = str(message.author.id)
	if user_id not in user_xp:
		user_xp[user_id] = {'xp': 0, 'messages': 0, 'last_message_time': '', 'last_message': ''}

	xp_gain = 5 + (10 if len(message.attachments) > 0 else 0)
	user_xp[user_id]['xp'] += xp_gain
	user_xp[user_id]['messages'] += 1
	user_xp[user_id]['last_message_time'] = str(message.created_at)
	user_xp[user_id]['last_message'] = str(message.content)

	save_user_data()
	await bot.process_commands(message)

@bot.command(name='xp')
async def xp(ctx):
	user_id = str(ctx.author.id)
	user_info = user_xp.get(user_id, {'xp': 0, 'messages': 0, 'last_message_time': ''})
	xp = user_info['xp']
	rank, color = get_rank(xp)

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
	user_id = str(ctx.author.id)
	user_info = user_xp.get(user_id, {'xp': 0, 'messages': 0, 'last_message_time': ''})
	xp = user_info['xp']
	rank, _ = get_rank(xp)

	if rank in ['Silver', 'Gold', 'Diamond', 'Platinum']:
		deleted = await ctx.channel.purge(limit=20)
		await ctx.send(f'Deleted {len(deleted)} message(s)', delete_after=5)
	else:
		await ctx.send('You need to be at least Silver rank to use this command.', delete_after=5)

bot.run('')
