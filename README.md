# queue

Website for online queue where admin can accept students, and where students can queue live or electronically (in advance via bot).

Two sites for admins(web version only) and users(mobile version only)
Launching mobile and web versions
1) Launch mobile _main_.py file
2) Run web app.py file
3)Database app.sql
Launch Telegram bot
1)Launch eletronic queue.py,telegram_bot_queue.py
2)Enter the place token YOUR bot = telebot.TeleBot('YOUR KEY')

How get token?
Instructions for creating a bot token (BotFather)
Users who start running channels in messenger often don't know where to get a bot token in Telegram. The thing is that the messenger itself has the “father” of all bots - it is a channel called @botfather. It is there that you will be able to find your bot token. 

The following instruction will show you how to get a Telegram bot token:

-Open the messenger on your PC or phone.
-Type the word “@botfather” in the search box.
-Type the word “@botfather” in the search box
-Go to the dialog and click on the “Start” button.
-Go to the dialog and click the “Start” button.
-The program will give you a list of commands that you can use to control BotFather.
-Choose the command called “/new_bot”. This is the one that will give you the ability to create a token for your bot in Telegram.
-Select the command that is called “/new_bot”
-Next, the system will ask you to spell out the name of your bot. Give it a name, type it in the reply line and send it to BotFather.
-Next, the system will ask for the name of your bot. Give it a name.
-After this procedure, the system will ask for the nickname of the future bot, it must contain the prefix “_bot”.
-If the nickname will coincide with those names that are already in the system, it will reject it. Therefore, think up an original nickname, type it in and wait until the system accepts your variant.
-Setting an original nickname in Botfather
-After the acceptance procedure has passed, BotFather will display the bot token.


Libraries
pip install Flask
pip install psycopg2
pip install telebot
