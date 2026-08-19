from bot.bot import start_bot
from models.models import init_db

def main():
    start_bot()

if __name__ == '__main__':
    init_db()
    main()