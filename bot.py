# bot.py - SECURE VERSION
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import random
import os
import re
from datetime import datetime, date
from dotenv import load_dotenv

# -------------------------
# CONFIG - ENVIRONMENT VARIABLES (SECURE)
# -------------------------
load_dotenv()  # Load from .env file (local) or Railway variables

# Get token from environment - NEVER hardcode real token!
TOKEN = os.getenv('TOKEN')

# For local testing only - this placeholder is safe to share
if not TOKEN:
    TOKEN = "PASTE_YOUR_TOKEN_HERE_FOR_LOCAL_TESTING_ONLY"
    print("⚠️  WARNING: Using placeholder token. For production, set TOKEN environment variable.")
    print("⚠️  Create a .env file with TOKEN=your_bot_token or set in Railway Variables")

# Channel IDs
CARD_PULLS_CHANNEL_ID = 1438858672380973137      # where /card can be used
CARD_COLLECTION_CHANNEL_ID = 1438858759903379608  # public announcement channel
COLLECTION_CHANNEL_ID = 1438858759903379608        # 🃏・card-collection channel
LEADERBOARD_CHANNEL_ID = 1444904908326174891       # leaderboard channel

CARDS_FOLDER = "./cards"
DB_PATH = "cards.db"
PULLS_PER_DAY = 50  # For testing

# Admin user IDs who can use /reloadcards
ADMIN_IDS = [123456789012345678]  # Replace with YOUR Discord ID

# -------------------------
# RARITY CONFIG
# -------------------------
RARITY_CHANCES = {
    "Common": 50.0,
    "Uncommon": 25.0,
    "Rare": 15.0,
    "Epic": 7.5,
    "Legendary": 2.5
}

RARITY_COLORS = {
    "Common": 0x808080,      # gray
    "Uncommon": 0x00FF00,    # green
    "Rare": 0x0000FF,        # blue
    "Epic": 0x800080,        # purple
    "Legendary": 0xFFD700    # gold
}

# -------------------------
# CARD LISTS
# -------------------------
CARDS_BY_RARITY = {
    "Legendary": ["Pokimane", "SSSniperwolf", "Valkyrae", "Azzyland"],
    "Epic": ["Andrea Botez", "Cinna", "Sommer Ray", "Alexandra Botez"],
    "Rare": ["StrawberryTabby", "Sara Saffari", "Corinna Kopf", "Alinity",
             "Sweet Anita", "QuarterJade", "Lauren Alexis", "Loserfruit", "Hyoon"],
    "Uncommon": ["Tinakitten", "Emiru", "Susu", "xChocoBars", "Fuslie", "Talia Mar",
                 "Bella Poarch", "Neekolul", "Brooke Monk", "STPeach", "Alissa Violet",
                 "Hannah OwO", "Amouranth", "Tara Yummy", "Heyimbee"],
    "Common": ["AngelsKimi", "AriaSaki", "BrookeAB", "ExtraEmily", "Fanfan",
               "iGumdrop", "JustaMinx", "Kyedae", "LilyPichu", "QTCinderella",
               "Maya Higa", "Sommerset", "Starsmitten", "Supcaitlin", "Syanne",
               "Sydeon", "Yvonnie", "Emma Langevin", "Faith Ordway", "Sakura"]
}

TOTAL_UNIQUE_CARDS = sum(len(v) for v in CARDS_BY_RARITY.values())

# Global variable for card images
CARD_IMAGE_MAP = {}

# -------------------------
# DATABASE FUNCTIONS
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS pulls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            card_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            pull_date TEXT NOT NULL,
            pull_time TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

init_db()

def record_pull(user_id, user_name, card_name, rarity):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO pulls (user_id, user_name, card_name, rarity, pull_date, pull_time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(user_id), str(user_name), card_name, rarity, str(date.today()), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def pulls_count_today(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM pulls
        WHERE user_id = ? AND pull_date = ?
    ''', (str(user_id), str(date.today())))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_collection_counts(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT card_name, COUNT(*) as cnt
        FROM pulls
        WHERE user_id = ?
        GROUP BY card_name
        ORDER BY cnt DESC, card_name ASC
    ''', (str(user_id),))
    rows = c.fetchall()
    conn.close()
    return rows

def get_card_pull_count(user_id, card_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM pulls WHERE user_id = ? AND card_name = ?
    ''', (str(user_id), card_name))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_leaderboard():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT user_id, user_name, COUNT(DISTINCT card_name) as unique_count
        FROM pulls 
        GROUP BY user_id 
        ORDER BY unique_count DESC 
        LIMIT 10
    ''')
    rows = c.fetchall()
    conn.close()
    return rows

# -------------------------
# IMAGE LOADING
# -------------------------
def normalize(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

def load_card_image_map():
    files = {}
    if not os.path.isdir(CARDS_FOLDER):
        os.makedirs(CARDS_FOLDER, exist_ok=True)
        print(f"Created {CARDS_FOLDER} — add your .png files there.")
        return files

    for fname in os.listdir(CARDS_FOLDER):
        lower = fname.lower()
        if not lower.endswith(".png") and not lower.endswith(".png.png"):
            continue
        base = lower.replace(".png.png", "").replace(".png", "")
        key = normalize(base)
        files[key] = fname
    print(f"Loaded {len(files)} image files from {CARDS_FOLDER}")
    return files

CARD_IMAGE_MAP = load_card_image_map()

def pick_rarity():
    rarities = list(RARITY_CHANCES.keys())
    weights = [RARITY_CHANCES[r] for r in rarities]
    return random.choices(rarities, weights=weights, k=1)[0]

# -------------------------
# BOT SETUP
# -------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Slash sync warning:", e)
    print(f"✅ Bot connected as {bot.user}")
    print(f"✅ Total cards: {TOTAL_UNIQUE_CARDS}")
    print(f"✅ Images loaded: {len(CARD_IMAGE_MAP)}")

# -------------------------
# /card COMMAND
# -------------------------
@bot.tree.command(name="card", description="Pull a streamer card (50 pulls per day for testing).")
async def card(interaction: discord.Interaction):
    if interaction.channel_id != CARD_PULLS_CHANNEL_ID:
        await interaction.response.send_message("⛔ This command can only be used in the card-pulls channel.", ephemeral=True)
        return

    user = interaction.user
    user_id = user.id

    if pulls_count_today(user_id) >= PULLS_PER_DAY:
        await interaction.response.send_message(f"⛔ You already used your {PULLS_PER_DAY} pulls today!", ephemeral=True)
        return

    rarity = pick_rarity()
    pool = CARDS_BY_RARITY.get(rarity, [])
    if not pool:
        await interaction.response.send_message("⚠️ No cards configured for this rarity.", ephemeral=True)
        return

    card_name = random.choice(pool)
    key = normalize(card_name)

    if key not in CARD_IMAGE_MAP:
        record_pull(user_id, user.display_name, card_name, rarity)
        await interaction.response.send_message(f"🎉 You pulled a **{rarity}** card!\n**Card:** {card_name}\n\n(Warning: image missing for this card.)")
        drops_channel = bot.get_channel(CARD_COLLECTION_CHANNEL_ID)
        if drops_channel:
            await drops_channel.send(f"🎴 **{user.display_name}** pulled a **{rarity}** card: **{card_name}**! (image missing)")
        return

    current_pull_count = get_card_pull_count(user_id, card_name)
    was_unique = current_pull_count == 0
    record_pull(user_id, user.display_name, card_name, rarity)
    updated_pull_count = current_pull_count + 1

    img_file = CARD_IMAGE_MAP[key]
    img_path = os.path.join(CARDS_FOLDER, img_file)

    rows = get_collection_counts(user_id)
    unique_owned = len(rows)

    description_parts = [
        f"**Rarity:** {rarity} — **{RARITY_CHANCES[rarity]}%**",
        f"**Unique Cards:** {unique_owned} / {TOTAL_UNIQUE_CARDS}"
    ]
    
    if not was_unique:
        description_parts.append(f"**Duplicate** (x{updated_pull_count})")

    embed = discord.Embed(
        title=f"🎉 {user.display_name} pulled {card_name}!",
        description="\n".join(description_parts),
        color=RARITY_COLORS.get(rarity, 0xFFFFFF)
    )

    try:
        file = discord.File(img_path, filename="card.png")
        embed.set_image(url="attachment://card.png")
        await interaction.response.send_message(file=file, embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"🎉 {user.display_name} pulled a **{rarity}** card!\n**Card:** {card_name}\n(Warning: failed to attach image)")
        print("Failed to attach image:", e)

    drops_channel = bot.get_channel(CARD_COLLECTION_CHANNEL_ID)
    if drops_channel and drops_channel.id != interaction.channel_id:
        try:
            duplicate_text = "" if was_unique else f" (duplicate x{updated_pull_count})"
            await drops_channel.send(f"🎴 **{user.display_name}** pulled a **{rarity}** card: **{card_name}**!{duplicate_text}")
        except Exception as e:
            print("Failed to announce in collection channel:", e)

# -------------------------
# /collection COMMAND
# -------------------------
@bot.tree.command(name="collection", description="View your public card collection.")
async def collection(interaction: discord.Interaction):
    if interaction.channel_id != COLLECTION_CHANNEL_ID:
        await interaction.response.send_message(f"⛔ This command can only be used in the <#{COLLECTION_CHANNEL_ID}> channel.", ephemeral=True)
        return

    user = interaction.user
    rows = get_collection_counts(user.id)
    if not rows:
        await interaction.response.send_message(f"📭 {user.display_name} has no cards yet!")
        return

    total_owned_unique = len(rows)
    owned = {card: cnt for card, cnt in rows}

    embed = discord.Embed(
        title=f"{user.display_name}'s Collection — {total_owned_unique}/{TOTAL_UNIQUE_CARDS} unique",
        color=0x00FFAA
    )

    for rarity in ["Legendary", "Epic", "Rare", "Uncommon", "Common"]:
        names = CARDS_BY_RARITY.get(rarity, [])
        lines = []
        for n in names:
            cnt = owned.get(n, 0)
            if cnt > 0:
                if cnt > 1:
                    lines.append(f"• **{n}** x{cnt}")
                else:
                    lines.append(f"• **{n}**")
        if lines:
            embed.add_field(
                name=f"{rarity} ({RARITY_CHANCES[rarity]}%)", 
                value="\n".join(lines), 
                inline=False
            )

    await interaction.response.send_message(embed=embed)

# -------------------------
# /leaderboard COMMAND
# -------------------------
@bot.tree.command(name="leaderboard", description="View the top 10 collectors by unique cards.")
async def leaderboard(interaction: discord.Interaction):
    if interaction.channel_id != LEADERBOARD_CHANNEL_ID:
        await interaction.response.send_message(f"⛔ This command can only be used in the <#{LEADERBOARD_CHANNEL_ID}> channel.", ephemeral=True)
        return

    leaderboard_data = get_leaderboard()
    
    if not leaderboard_data:
        await interaction.response.send_message("📊 No one has collected any cards yet! Be the first!")
        return

    embed = discord.Embed(
        title="🏆 Card Collection Leaderboard",
        description=f"Top 10 collectors by unique cards collected\nTotal available: {TOTAL_UNIQUE_CARDS} cards",
        color=0xFFD700
    )

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    leaderboard_text = []
    for i, (user_id, user_name, unique_count) in enumerate(leaderboard_data):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        leaderboard_text.append(f"{medal} **{user_name}** - {unique_count}/{TOTAL_UNIQUE_CARDS} unique cards")
    
    embed.add_field(
        name="Top Collectors",
        value="\n".join(leaderboard_text),
        inline=False
    )

    await interaction.response.send_message(embed=embed)

# -------------------------
# /reloadcards COMMAND
# -------------------------
@bot.tree.command(name="reloadcards", description="[ADMIN] Reload card images without restarting bot.")
async def reloadcards(interaction: discord.Interaction):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("⛔ You don't have permission to use this command.", ephemeral=True)
        return

    global CARD_IMAGE_MAP
    try:
        old_count = len(CARD_IMAGE_MAP)
        CARD_IMAGE_MAP = load_card_image_map()
        new_count = len(CARD_IMAGE_MAP)
        
        embed = discord.Embed(
            title="🔄 Card Images Reloaded",
            description=f"Successfully reloaded card images!\n**Before:** {old_count} images\n**After:** {new_count} images",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Reload Failed",
            description=f"Error reloading card images: {str(e)}",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

# -------------------------
# RUN BOT
# -------------------------
if __name__ == "__main__":
    if TOKEN == "PASTE_YOUR_TOKEN_HERE_FOR_LOCAL_TESTING_ONLY":
        print("⚠️  IMPORTANT: For production, set the TOKEN environment variable!")
        print("⚠️  On Railway: Add TOKEN variable in Variables tab")
        print("⚠️  Locally: Create .env file with TOKEN=your_bot_token")
    
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ ERROR: Invalid bot token!")
        print("❌ Make sure TOKEN is set correctly in environment variables")
        print("❌ On Railway: Check Variables tab")
        print("❌ Locally: Check .env file")