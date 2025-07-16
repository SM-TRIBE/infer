# main.py
# This is the main entry point for the Telegram bot.
# It handles the bot's lifecycle, command routing, and conversation management.

import logging
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

# Import database functions and utility functions
import db
import utils

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(
    GENDER,
    AGE,
    BIO,
    PHOTO,
    LOCATION,
    MENU,
    SEARCH_GENDER,
    SEARCH_AGE_MIN,
    SEARCH_AGE_MAX,
    VIEW_PROFILE,
    ADMIN_MENU,
    ADMIN_GRANT_COINS,
    ADMIN_GRANT_PREMIUM,
    ADMIN_USER_LIST,
    ADMIN_BAN_USER,
    ADMIN_UNBAN_USER,
) = range(16)

# --- Helper Functions ---

async def get_user_profile_text(user_id):
    """Generates the text for a user's profile."""
    profile_data = await db.get_user_profile(user_id)
    if not profile_data:
        return "Profile not found."

    premium_status = "Yes" if profile_data["is_premium"] else "No"
    return (
        f"<b>Name:</b> {profile_data['name']}\n"
        f"<b>Gender:</b> {profile_data['gender']}\n"
        f"<b>Age:</b> {profile_data['age']}\n"
        f"<b>Bio:</b> {profile_data['bio']}\n"
        f"<b>Location:</b> {profile_data['location']}\n"
        f"<b>Coins:</b> {profile_data['coins']}\n"
        f"<b>Premium:</b> {premium_status}"
    )


# --- Start and Profile Creation ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the user's gender."""
    user = update.message.from_user
    user_id = user.id
    referral_code = context.args[0] if context.args else None

    if await db.user_exists(user_id):
        await update.message.reply_text("Welcome back! You can access the menu with /menu.")
        return ConversationHandler.END

    await db.create_user(user_id, user.first_name, referral_code)

    reply_keyboard = [["Male", "Female", "Other"]]
    await update.message.reply_text(
        "Hi! Welcome to the Dating Bot. Let's create your profile. "
        "First, what is your gender?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return GENDER


async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the gender and asks for age."""
    user_id = update.message.from_user.id
    user_gender = update.message.text
    await db.update_profile(user_id, "gender", user_gender)
    await update.message.reply_text("Great! Now, how old are you?")
    return AGE


async def age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the age and asks for a bio."""
    user_id = update.message.from_user.id
    try:
        user_age = int(update.message.text)
        if not 18 <= user_age <= 99:
            raise ValueError
        await db.update_profile(user_id, "age", user_age)
        await update.message.reply_text("Got it. Now, write a short bio about yourself.")
        return BIO
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid age (between 18 and 99).")
        return AGE


async def bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the bio and asks for a photo."""
    user_id = update.message.from_user.id
    user_bio = update.message.text
    await db.update_profile(user_id, "bio", user_bio)
    await update.message.reply_text(
        "Nice bio! Now, please send a photo of yourself.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PHOTO


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo and asks for location."""
    user_id = update.message.from_user.id
    photo_file = await update.message.photo[-1].get_file()
    await db.update_profile(user_id, "photo_id", photo_file.file_id)
    await update.message.reply_text(
        "Looking good! Finally, what's your location (e.g., city, country)?"
    )
    return LOCATION


async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the location and ends the profile creation."""
    user_id = update.message.from_user.id
    user_location = update.message.text
    await db.update_profile(user_id, "location", user_location)
    await update.message.reply_text(
        "Your profile is complete! You can now use the bot's features. "
        "Use /menu to see what you can do."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "Operation cancelled.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# --- Main Menu ---

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the main menu."""
    keyboard = [
        [InlineKeyboardButton("Search for others", callback_data="search")],
        [InlineKeyboardButton("View my profile", callback_data="my_profile")],
        [InlineKeyboardButton("Referral System", callback_data="referral")],
        [InlineKeyboardButton("Store", callback_data="store")],
    ]
    if await db.is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("Admin Menu", callback_data="admin_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Main Menu:", reply_markup=reply_markup)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles menu button presses."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "search":
        reply_keyboard = [["Male", "Female", "Other"]]
        await query.edit_message_text(
            "Who are you interested in?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return SEARCH_GENDER
    elif query.data == "my_profile":
        profile_text = await get_user_profile_text(user_id)
        profile_data = await db.get_user_profile(user_id)
        if profile_data and profile_data.get("photo_id"):
            await context.bot.send_photo(
                chat_id=user_id,
                photo=profile_data["photo_id"],
                caption=profile_text,
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(profile_text, parse_mode="HTML")
        return ConversationHandler.END
    elif query.data == "referral":
        referral_code = await db.get_referral_code(user_id)
        referral_count = await db.get_referral_count(user_id)
        await query.edit_message_text(
            f"Your referral code is: `{referral_code}`\n"
            f"Share this code with your friends. You'll get 50 coins for each friend who joins!\n"
            f"You have successfully referred {referral_count} users.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    elif query.data == "store":
        await query.edit_message_text("Store coming soon!")
        return ConversationHandler.END
    elif query.data == "admin_menu":
        return await admin_menu_command(update, context)

    return ConversationHandler.END


# --- Search ---

async def search_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the preferred gender and asks for min age."""
    context.user_data["search_gender"] = update.message.text
    await update.message.reply_text("What's the minimum age you're looking for?")
    return SEARCH_AGE_MIN


async def search_age_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the min age and asks for max age."""
    try:
        min_age = int(update.message.text)
        if not 18 <= min_age <= 99:
            raise ValueError
        context.user_data["search_age_min"] = min_age
        await update.message.reply_text("And the maximum age?")
        return SEARCH_AGE_MAX
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid age (between 18 and 99).")
        return SEARCH_AGE_MIN


async def search_age_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the max age and performs the search."""
    try:
        max_age = int(update.message.text)
        min_age = context.user_data["search_age_min"]
        if not min_age <= max_age <= 99:
            raise ValueError

        gender_pref = context.user_data["search_gender"]
        user_id = update.message.from_user.id

        results = await db.search_users(user_id, gender_pref, min_age, max_age)

        if not results:
            await update.message.reply_text("No users found matching your criteria.")
            return ConversationHandler.END

        context.user_data["search_results"] = results
        context.user_data["search_index"] = 0
        await view_profile(update, context)
        return VIEW_PROFILE

    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid age greater than or equal to the minimum age.")
        return SEARCH_AGE_MAX

async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays a profile from the search results."""
    results = context.user_data.get("search_results", [])
    index = context.user_data.get("search_index", 0)

    if not results or index >= len(results):
        await update.message.reply_text("No more profiles to show.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    target_user_id = results[index]["user_id"]
    profile_text = await get_user_profile_text(target_user_id)
    profile_data = await db.get_user_profile(target_user_id)

    keyboard = [
        [
            InlineKeyboardButton("Like ❤️", callback_data=f"like_{target_user_id}"),
            InlineKeyboardButton("Next ➡️", callback_data="next_profile"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if profile_data.get("photo_id"):
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=profile_data["photo_id"],
            caption=profile_text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(
            profile_text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    return VIEW_PROFILE


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles button presses on profiles (Like, Next)."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("like_"):
        target_user_id = int(data.split("_")[1])
        # In a real app, you'd handle the "like" logic (e.g., check for a match)
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"Someone liked your profile! You can view their profile by searching for them."
        )
        await query.edit_message_text("You liked this profile!")
        # Move to the next profile automatically after liking
        context.user_data["search_index"] += 1
        # Need to use a different message to trigger the next profile view
        await context.bot.send_message(chat_id=user_id, text="Loading next profile...")
        await view_profile(query, context) # Re-use query to send new message
        return VIEW_PROFILE

    elif data == "next_profile":
        context.user_data["search_index"] += 1
        await query.delete_message()
        await view_profile(query, context) # Re-use query to send new message
        return VIEW_PROFILE

    return VIEW_PROFILE

# --- Admin ---

async def admin_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the admin menu."""
    user_id = update.effective_user.id
    if not await db.is_admin(user_id):
        # This check is also in the main menu, but good to have it here too.
        await update.callback_query.edit_message_text("You are not authorized to use this command.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("List Users", callback_data="admin_list_users")],
        [InlineKeyboardButton("Grant Coins", callback_data="admin_grant_coins")],
        [InlineKeyboardButton("Grant Premium", callback_data="admin_grant_premium")],
        [InlineKeyboardButton("Ban User", callback_data="admin_ban_user")],
        [InlineKeyboardButton("Unban User", callback_data="admin_unban_user")],
        [InlineKeyboardButton("Back to Main Menu", callback_data="main_menu_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("Admin Menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Admin Menu:", reply_markup=reply_markup)
    return ADMIN_MENU

async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles admin menu button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "admin_list_users":
        # In a real bot with many users, you would paginate this.
        users = await db.get_all_users()
        if not users:
            await query.edit_message_text("No users found.")
            return ADMIN_MENU

        user_list = "<b>List of Users:</b>\n\n"
        for user in users:
            user_list += f"ID: <code>{user['user_id']}</code>, Name: {user['name']}, Banned: {'Yes' if user['is_banned'] else 'No'}\n"

        await query.edit_message_text(user_list, parse_mode="HTML")
        # Return to admin menu after a delay or with a button
        return ADMIN_MENU

    elif query.data == "admin_grant_coins":
        await query.edit_message_text("Enter the User ID and amount of coins to grant (e.g., 12345678 100).")
        return ADMIN_GRANT_COINS

    elif query.data == "admin_grant_premium":
        await query.edit_message_text("Enter the User ID to grant premium status to.")
        return ADMIN_GRANT_PREMIUM

    elif query.data == "admin_ban_user":
        await query.edit_message_text("Enter the User ID to ban.")
        return ADMIN_BAN_USER

    elif query.data == "admin_unban_user":
        await query.edit_message_text("Enter the User ID to unban.")
        return ADMIN_UNBAN_USER

    elif query.data == "main_menu_back":
        # This is a bit tricky in ConversationHandler. A simple message is easier.
        await query.edit_message_text("Returning to main menu... Use /menu to bring it up again.")
        return ConversationHandler.END

    return ADMIN_MENU

async def admin_grant_coins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Grants coins to a user."""
    try:
        user_id_str, amount_str = update.message.text.split()
        target_user_id = int(user_id_str)
        amount = int(amount_str)

        if not await db.user_exists(target_user_id):
            await update.message.reply_text("User not found.")
            return ADMIN_MENU

        await db.add_coins(target_user_id, amount)
        await update.message.reply_text(f"Successfully granted {amount} coins to user {target_user_id}.")
        await context.bot.send_message(chat_id=target_user_id, text=f"An admin has granted you {amount} coins!")

    except (ValueError, IndexError):
        await update.message.reply_text("Invalid format. Please use: UserID Amount")

    # Go back to admin menu
    await admin_menu_command(update, context)
    return ADMIN_MENU


async def admin_grant_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Grants premium status to a user."""
    try:
        target_user_id = int(update.message.text)
        if not await db.user_exists(target_user_id):
            await update.message.reply_text("User not found.")
            return ADMIN_MENU

        await db.set_premium_status(target_user_id, True)
        await update.message.reply_text(f"Successfully granted premium status to user {target_user_id}.")
        await context.bot.send_message(chat_id=target_user_id, text="An admin has granted you premium status!")

    except ValueError:
        await update.message.reply_text("Invalid User ID.")

    await admin_menu_command(update, context)
    return ADMIN_MENU

async def admin_ban_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE, ban: bool) -> int:
    """Bans or unbans a user."""
    try:
        target_user_id = int(update.message.text)
        if not await db.user_exists(target_user_id):
            await update.message.reply_text("User not found.")
            return ADMIN_MENU

        await db.set_ban_status(target_user_id, ban)
        action = "banned" if ban else "unbanned"
        await update.message.reply_text(f"Successfully {action} user {target_user_id}.")
        await context.bot.send_message(chat_id=target_user_id, text=f"An admin has {action} you.")

    except ValueError:
        await update.message.reply_text("Invalid User ID.")

    await admin_menu_command(update, context)
    return ADMIN_MENU

async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await admin_ban_unban_user(update, context, ban=True)

async def admin_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await admin_ban_unban_user(update, context, ban=False)


# --- Main Function ---

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN environment variable not set.")

    application = Application.builder().token(token).build()

    # Conversation handler for profile creation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(filters.Regex("^(Male|Female|Other)$"), gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, bio)],
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for search
    search_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_callback, pattern="^search$")],
        states={
            SEARCH_GENDER: [MessageHandler(filters.Regex("^(Male|Female|Other)$"), search_gender)],
            SEARCH_AGE_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_age_min)],
            SEARCH_AGE_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_age_max)],
            VIEW_PROFILE: [CallbackQueryHandler(profile_callback, pattern="^(like_|next_profile)")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    # Conversation handler for admin menu
    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_menu_callback, pattern="^admin_")],
        states={
            ADMIN_MENU: [CallbackQueryHandler(admin_menu_callback)],
            ADMIN_GRANT_COINS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_grant_coins)],
            ADMIN_GRANT_PREMIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_grant_premium)],
            ADMIN_BAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_user)],
            ADMIN_UNBAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unban_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    application.add_handler(conv_handler)
    application.add_handler(search_conv_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("admin", admin_menu_command))
    application.add_handler(CallbackQueryHandler(menu_callback))


    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    # Initialize the database
    import asyncio
    asyncio.run(db.init_db())
    main()
