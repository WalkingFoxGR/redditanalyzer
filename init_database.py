"""
Manual Database Initialization Script
Run this if tables are not being created automatically
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

async def init_database():
    """Initialize all database tables"""

    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in .env file")
        print("\nAdd this to your .env file:")
        print("DATABASE_URL=postgresql://postgres:PASSWORD@db.xxx.supabase.co:6543/postgres")
        return

    print("=" * 60)
    print("  Database Initialization")
    print("=" * 60)
    print(f"\nConnecting to database...")
    print(f"Host: {DATABASE_URL.split('@')[1].split(':')[0] if '@' in DATABASE_URL else 'unknown'}")

    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected successfully!")

        print("\n📋 Creating tables...")

        # 1. Users table
        print("   → users table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by BIGINT,
                last_seen TIMESTAMP,
                coin_balance INTEGER DEFAULT 10,
                coins_expire_at TIMESTAMP,
                total_coins_purchased INTEGER DEFAULT 0,
                free_coins_claimed BOOLEAN DEFAULT TRUE
            )
        """)

        # 2. Coin transactions table
        print("   → coin_transactions table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS coin_transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                transaction_type TEXT,
                amount INTEGER,
                balance_after INTEGER,
                description TEXT,
                stripe_payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_coin_transactions_user_id
            ON coin_transactions(user_id)
        """)

        # 3. Coin packages table
        print("   → coin_packages table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS coin_packages (
                id SERIAL PRIMARY KEY,
                package_name TEXT,
                coins INTEGER,
                price_usd DECIMAL(10, 2),
                stripe_price_id TEXT,
                bonus_coins INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Payment history table
        print("   → payment_history table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                stripe_payment_intent TEXT UNIQUE,
                stripe_session_id TEXT,
                amount_usd DECIMAL(10, 2),
                coins_purchased INTEGER,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # 5. Command costs table
        print("   → command_costs table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS command_costs (
                command TEXT PRIMARY KEY,
                cost INTEGER,
                description TEXT
            )
        """)

        # 6. Usage logs table
        print("   → usage_logs table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                username TEXT,
                first_name TEXT,
                command TEXT,
                params TEXT,
                coins_spent INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_logs_timestamp
            ON usage_logs(timestamp DESC)
        """)

        # 7. Admin actions table
        print("   → admin_actions table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_actions (
                id SERIAL PRIMARY KEY,
                admin_id BIGINT REFERENCES users(user_id),
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 8. Bot statistics table
        print("   → bot_stats table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                id SERIAL PRIMARY KEY,
                stat_name TEXT UNIQUE,
                stat_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        print("\n💰 Inserting default coin packages...")
        default_packages = [
            ('Starter Pack', 20, 9.99, None, 0),
            ('Basic Pack', 50, 19.99, None, 5),
            ('Pro Pack', 100, 34.99, None, 15),
            ('Premium Pack', 250, 74.99, None, 50),
            ('Ultimate Pack', 500, 139.99, None, 150),
        ]

        for package in default_packages:
            await conn.execute("""
                INSERT INTO coin_packages
                (package_name, coins, price_usd, stripe_price_id, bonus_coins)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
            """, *package)
            print(f"   → {package[0]}: {package[1]} coins + {package[4]} bonus = ${package[2]}")

        print("\n⚙️  Inserting default command costs...")
        default_costs = [
            ('analyze', 2, 'Full subreddit analysis'),
            ('requirements', 2, 'Posting requirements check'),
            ('compare', 5, 'Compare multiple subreddits'),
            ('search', 1, 'Search for subreddits'),
            ('niche', 3, 'Niche community analysis'),
            ('rules', 1, 'Get subreddit rules'),
        ]

        for cost_data in default_costs:
            await conn.execute("""
                INSERT INTO command_costs (command, cost, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (command) DO UPDATE SET
                    cost = EXCLUDED.cost,
                    description = EXCLUDED.description
            """, *cost_data)
            print(f"   → /{cost_data[0]}: {cost_data[1]} coins - {cost_data[2]}")

        # Get table counts
        print("\n📊 Verifying tables...")
        tables = ['users', 'coin_transactions', 'coin_packages', 'payment_history',
                  'command_costs', 'usage_logs', 'admin_actions', 'bot_stats']

        for table in tables:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"   ✅ {table}: {count} rows")

        await conn.close()

        print("\n" + "=" * 60)
        print("  ✅ Database initialized successfully!")
        print("=" * 60)
        print("\nYour bot is ready to use! Send /start on Telegram to test it.")

    except asyncpg.PostgresError as e:
        print(f"\n❌ Database error: {e}")
        print("\nCommon issues:")
        print("  1. Wrong password in DATABASE_URL")
        print("  2. Wrong host/port (use port 6543 for Vercel)")
        print("  3. Database not accessible from your IP")
        print("  4. Supabase project paused")

    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(init_database())
