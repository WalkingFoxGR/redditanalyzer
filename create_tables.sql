-- Reddit Analyzer Bot - Database Tables
-- Paste this entire script into Supabase SQL Editor and run it

-- 1. Users table (main user data with coins)
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
);

-- 2. Coin transactions table (transaction history)
CREATE TABLE IF NOT EXISTS coin_transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    transaction_type TEXT,
    amount INTEGER,
    balance_after INTEGER,
    description TEXT,
    stripe_payment_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_coin_transactions_user_id
ON coin_transactions(user_id);

-- 3. Coin packages table (available packages to purchase)
CREATE TABLE IF NOT EXISTS coin_packages (
    id SERIAL PRIMARY KEY,
    package_name TEXT,
    coins INTEGER,
    price_usd DECIMAL(10, 2),
    stripe_price_id TEXT,
    bonus_coins INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Payment history table (Stripe payments)
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
);

-- 5. Command costs table (how much each command costs)
CREATE TABLE IF NOT EXISTS command_costs (
    command TEXT PRIMARY KEY,
    cost INTEGER,
    description TEXT
);

-- 6. Usage logs table (track all command usage)
CREATE TABLE IF NOT EXISTS usage_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    username TEXT,
    first_name TEXT,
    command TEXT,
    params TEXT,
    coins_spent INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster log queries
CREATE INDEX IF NOT EXISTS idx_usage_logs_timestamp
ON usage_logs(timestamp DESC);

-- 7. Admin actions table (log admin activities)
CREATE TABLE IF NOT EXISTS admin_actions (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT REFERENCES users(user_id),
    action TEXT,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Bot statistics table (general bot stats)
CREATE TABLE IF NOT EXISTS bot_stats (
    id SERIAL PRIMARY KEY,
    stat_name TEXT UNIQUE,
    stat_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- Insert Default Data
-- ========================================

-- Insert default coin packages
INSERT INTO coin_packages (package_name, coins, price_usd, stripe_price_id, bonus_coins)
VALUES
    ('Starter Pack', 20, 9.99, NULL, 0),
    ('Basic Pack', 50, 19.99, NULL, 5),
    ('Pro Pack', 100, 34.99, NULL, 15),
    ('Premium Pack', 250, 74.99, NULL, 50),
    ('Ultimate Pack', 500, 139.99, NULL, 150)
ON CONFLICT DO NOTHING;

-- Insert default command costs
INSERT INTO command_costs (command, cost, description)
VALUES
    ('analyze', 2, 'Full subreddit analysis'),
    ('requirements', 2, 'Posting requirements check'),
    ('compare', 5, 'Compare multiple subreddits'),
    ('search', 1, 'Search for subreddits'),
    ('niche', 3, 'Niche community analysis'),
    ('scrape', 0, 'Basic post scraping (free)'),
    ('scrape_ai_10', 2, 'AI recreation for 10 posts'),
    ('scrape_ai_20', 4, 'AI recreation for 20 posts'),
    ('scrape_ai_30', 6, 'AI recreation for 30 posts'),
    ('rules', 1, 'Get subreddit rules'),
    ('flairs', 1, 'Analyze flair performance'),
    ('discover', 10, 'Discover related subreddits (admin only)')
ON CONFLICT (command) DO UPDATE SET
    cost = EXCLUDED.cost,
    description = EXCLUDED.description;

-- Insert initial admin users (replace with your Telegram user ID)
INSERT INTO users (user_id, username, first_name, last_name, is_admin, is_active, coin_balance, coins_expire_at, free_coins_claimed)
VALUES
    (5028346767, 'panagiotis_krb', 'Panagiotis', 'Karampetsos', TRUE, TRUE, 999999, CURRENT_TIMESTAMP + INTERVAL '10 years', TRUE),
    (6150863409, NULL, 'Admin2', NULL, TRUE, TRUE, 999999, CURRENT_TIMESTAMP + INTERVAL '10 years', TRUE),
    (5157639618, NULL, 'Admin3', NULL, TRUE, TRUE, 999999, CURRENT_TIMESTAMP + INTERVAL '10 years', TRUE),
    (6923635816, NULL, 'Admin4', NULL, TRUE, TRUE, 999999, CURRENT_TIMESTAMP + INTERVAL '10 years', TRUE)
ON CONFLICT (user_id) DO UPDATE SET
    is_admin = TRUE,
    coin_balance = 999999,
    coins_expire_at = CURRENT_TIMESTAMP + INTERVAL '10 years';

-- ========================================
-- Verification Query
-- ========================================

-- Run this to verify tables were created
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND table_name IN ('users', 'coin_transactions', 'coin_packages', 'payment_history',
                       'command_costs', 'usage_logs', 'admin_actions', 'bot_stats')
ORDER BY table_name;
