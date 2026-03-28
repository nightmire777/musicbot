import discord
from discord.ext import commands
import yt_dlp
import asyncio

import os
from dotenv import load_dotenv



atago = commands.Bot(command_prefix='!', intents=discord.Intents.all())
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
FFMPEG_EXECUTABLE_PATH =  os.getenv('FFMPEG_PATH', 'ffmpeg')

# 1. YTDL Options: Tells yt-dlp what information to extract
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'auto',  # Allows searching by song name, not just URL
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'source_address': '0.0.0.0', # Allows IPv6/IPv4
    'extractor_args': {
        'youtube': {
            'player_client': ['web_creator', 'ios'],  # uses innertube clients
        }
    },
}

# 2. FFmpeg Options: Ensures smooth streaming
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn' # -vn tells FFmpeg to ignore video data
}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url') # The direct stream URL
        self.webpage_url = data.get('webpage_url') # The YouTube link

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or discord.compat.get_event_loop()
        ydl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        
        # This runs yt-dlp asynchronously
        data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=not stream))

        # Handle search results (if the input was a search query)
        if 'entries' in data:
            # Take the first item from the search results
            data = data['entries'][0]

        # Use the URL of the audio stream for FFmpeg
        # FFmpegOpusAudio is more efficient than PCMAudio
        filename = data['url'] if stream else ydl.prepare_filename(data)
        
        return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_EXECUTABLE_PATH,**FFMPEG_OPTIONS), data=data)

import psutil
import os
# measuring bot usage
@atago.command(name='stats')
async def stats(ctx):
    process = psutil.Process(os.getpid())
    cpu = psutil.cpu_percent(interval=1)
    ram = process.memory_info().rss / 1024 / 1024  # convert to MB
    await ctx.send(f"CPU: {cpu}%\nRAM: {ram:.2f} MB")
    
global songQueue
songQueue = []

# shows the queue 
@atago.command(name='showq', help='shows the queue')
async def showq(ctx):
    if songQueue:
        queueText = '\n'.join([f"{idx+1}. {song.title}" for idx, song in enumerate(songQueue)])
        await ctx.send(f"**Current Queue:**\n{queueText}")
    else:
        await ctx.send("The queue is currently empty.")

#  helper function, adds a song to queue
async def queue(ctx, url):
    player = await YTDLSource.from_url(url, loop=atago.loop, stream=True)
    songQueue.append(player)
    await ctx.send(f'Added **{player.title}**')

# next song 
async def next(ctx):
    if songQueue:
        player = songQueue.pop(0)
        ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(next(ctx), atago.loop))
        await ctx.send(f'Now playing: **{player.title}**')
    else:
        await leave(ctx) 

# skip song
@atago.command(name='skip', help='Skips the current song')
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()  # this triggers the after callback which calls play_next
        await ctx.send('⏭️ Skipped!')
    else:
        await ctx.send('Nothing is playing.')

# play music
@atago.command(name='play', help='To play a local audio file (e.g., !play ./audio/song.mp3)')
async def play(ctx, *, url):
    # connect to vc 
    if (await join(ctx) == 1):
        return 
    else: 
        await queue(ctx, url=url)   

    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        await next(ctx)


# join vc 
@atago.command(name='join', help='Joins the VC you are in')
async def join(ctx):

    #  check if the author is actually in vc
    if not ctx.author.voice:
        await ctx.send(f"<@{ctx.author.id}> please join the VC first!")
        return 1
    
    # get the senders vc channel
    c = ctx.author.voice.channel

    # Check if the atago is already in a VC on the same guild
    if ctx.voice_client:
        await ctx.voice_client.move_to(c)
    else:
        # Connect to the voice channel
        await c.connect()
        
    #debug statement
    #await ctx.send(f"Joined {c.name}, <@{ctx.author.id}>")

    return 0 

# force her to leave vc
@atago.command(name='leave',help='either you came early or time is up, make her leave vc')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left VC")
    else:
        await ctx.send("Currently not in a VC")


# Now, this will work!
@atago.command()
async def hello(ctx):
    await ctx.send("Hello!")

atago.run(DISCORD_BOT_TOKEN)
