from datetime import (
    datetime, 
    timedelta, 
    timezone, 
)
from helpers import (
    format_date,
    format_seconds,
    is_after_with_offset,
)
import sqlite3

DATABASE_FILE = 'youtube_collections.db'
FRESHNESS_HOURS = 12

def init_db():
    """Create tables if they don't exist"""
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    
    # Users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL
        )
    ''')
    
    # Channels table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            refreshed_at TEXT,
            next_page_token TEXT,
            backfill_complete INTEGER NOT NULL DEFAULT 0 CHECK (backfill_complete IN (0,1))
        )
    ''')

    # Subscriptions table (lists subscribed channels for each user)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            subscribed_at TEXT,
            UNIQUE(channel_id, user_id),
            FOREIGN KEY (channel_id) REFERENCES channels (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Categories table (lists categories created by each user)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            UNIQUE(user_id, name),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Collections table (connects user categories to user subscriptions through many-to-many junction)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            UNIQUE(user_id, channel_id, category_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (channel_id) REFERENCES channels (id)
        )
    ''')

    # Videos table (caches fetched videos information)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            title TEXT,
            duration_seconds INTEGER CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
            published_at TEXT NOT NULL,
            refreshed_at TEXT,
            thumbnail_url TEXT,
            channel_id TEXT NOT NULL,
            FOREIGN KEY (channel_id) REFERENCES channels (id)
        )
    ''')

    # Table indices for faster frequent lookups
    cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at)")
    
    conn.commit()
    conn.close()

    print("Database initialized!")


def get_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def assign_category_to_channel(user_id, channel_id, category_id):
    """Assign category to channel (or unassign if category_id=0)"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()
    
        # FIRST: Remove ALL existing assignments for the channel
        cur.execute('''
            DELETE FROM collections 
            WHERE
                user_id = ? AND
                channel_id = ?
        ''', (user_id, channel_id))
        
        # THEN: Add new assignment (if not unassigning)
        if int(category_id) > 0:
            cur.execute('''
                INSERT INTO collections (user_id, channel_id, category_id)
                VALUES (?, ?, ?)
            ''', (user_id, channel_id, category_id))
        
        conn.commit()
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to assign channel {channel_id} to category {category_id}: {e}")
        raise

    finally:
        conn.close()


def create_category(category_name, user_id):
    """Create new category or return existing"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()
    
        # Check if category already exists for this user
        cur.execute('''
            SELECT id FROM categories
            WHERE
                name = ? AND
                user_id = ?
        ''', (category_name, user_id))
        existing = cur.fetchone()
        if existing:
            return 'EXISTS'
        
        # Create new category
        cur.execute('''
            INSERT INTO categories (name, user_id)
            VALUES (?, ?)
        ''', (category_name, user_id))
        conn.commit()
        return 'OK'

    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to create category {category_name}: {e}")
        raise

    finally:
        conn.close()


def delete_category(category_id, user_id):
    """Delete a category and all its channel assignments"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()
    
        # Check if category exists for this user
        cur.execute('''
            SELECT name
            FROM categories
            WHERE
                id = ? AND
                user_id = ?
        ''', (category_id, user_id))

        if not cur.fetchone():
            return False
        
        # Remove all channel assignments for this category for this user
        cur.execute('''
            DELETE FROM collections
            WHERE
                category_id = ? AND
                user_id = ?
        ''', (category_id, user_id))
        
        # Remove the category for this user
        cur.execute('''
            DELETE FROM categories
            WHERE
                id = ? AND
                user_id = ?
        ''', (category_id, user_id))
        
        conn.commit()
        return True
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to delete category {category_id}: {e}")
        raise

    finally:
        conn.close()


# UNUSED but kept as future-use cleanup utility
def delete_orphaned_channels():
    """Delete channels that are not in any user's subscriptions"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    try:
        cur = conn.cursor()
        cur.execute('''
            DELETE FROM channels
            WHERE id NOT IN (
                SELECT channel_id
                FROM subscriptions
            )
        ''')
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to delete orphaned channels: {e}")
        raise
    finally:
        conn.close()


# UNUSED but kept as future-use cleanup utility
def delete_orphaned_videos():
    """Delete cached videos from channels that are not in any user's subscriptions"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    try:
        cur = conn.cursor()
        cur.execute('''
            DELETE FROM videos
            WHERE channel_id NOT IN (
                SELECT channel_id
                FROM subscriptions
            )
        ''')
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to delete orphaned cached videos: {e}")
        raise
    finally:
        conn.close()


def get_categories(user_id):
    """Get user's category names + IDs"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        SELECT id, name
        FROM categories
        WHERE user_id = ?
    ''', (user_id,))

    categories = [{"category_id": r[0], "category_name": r[1]} for r in cur.fetchall()]

    conn.close()

    return categories


def get_channel_depth_info(channel_id, cursor=None, short_duration_seconds=150):
    conn = None
    if not cursor:
        conn = get_connection()
        cur = conn.cursor()
    else:
        cur = cursor

    try:
        cur.execute('''
            SELECT name, backfill_complete
            FROM channels
            WHERE id = ?
        ''', (channel_id,))

        row = cur.fetchone()
        if not row:
            print(f'get_channel_depth_info: channel_id {channel_id} not found')
            return None
        
        channel_depth_info = {
            "channel_id": channel_id,
            "channel_name": row[0],
            "backfill_complete": row[1],
            "published_at_oldest": None,
            "published_at_oldest_id": None,
        }

        cur.execute('''
            SELECT published_at, id
            FROM videos
            WHERE channel_id = ?
            ORDER BY published_at ASC, id ASC
            LIMIT 1
        ''', (channel_id,))

        row = cur.fetchone()

        if row:
            channel_depth_info.update({
                "published_at_oldest": row[0],
                "published_at_oldest_id": row[1],
            })

        return channel_depth_info
    
    finally:
        if conn:
            conn.close()


def get_channels_depth_info(channel_ids, short_duration_seconds=150):
    if not channel_ids:
        print('get_channels_depth_info: no channels')
        return []
    
    conn = get_connection()
    cur = conn.cursor()

    try:
        channels_depth_info = []
        for channel_id in channel_ids:
            channels_depth_info.append(get_channel_depth_info(channel_id, cursor=cur, short_duration_seconds=short_duration_seconds))
        return channels_depth_info
    
    finally:
        conn.close()


def get_channel_name(channel_id, cursor=None):
    """Get name of channel"""
    conn = None
    if not cursor:
        conn = get_connection()
        cur = conn.cursor()
    else:
        cur = cursor

    try:
        cur.execute('''
            SELECT name
            FROM channels
            WHERE id = ?
        ''', (channel_id,))
        
        row = cur.fetchone()
        return row[0] if row else None

    except Exception as e:
        print(f"❌ get_channel_name failed to get channel name for channel {channel_id}: {e}")
        raise

    finally:
        if conn:
            conn.close()


def get_channel_names(channel_ids):
    if not channel_ids:
        return []
    
    conn = get_connection()
    cur = conn.cursor()

    channel_names = []
    for channel_id in channel_ids:
        try:
            channel_name = get_channel_name(channel_id, cursor=cur)
            if channel_name is not None:
                channel_names.append(channel_name)
        except:
            continue

    conn.close()

    return channel_names


def get_channel_next_page_token(channel_id):
    """Get channel's saved next page token"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute('''
            SELECT next_page_token
            FROM channels
            WHERE id = ?
        ''', (channel_id,))
        row = cur.fetchone()
        return row[0] if row else None

    finally:
        conn.close()


def get_channel_video_youngest(channel_id):
    """Get channel's most recent video in database"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute('''
            SELECT id, published_at
            FROM videos
            WHERE channel_id = ?
            ORDER BY
                published_at DESC, 
                id DESC
            LIMIT 1
        ''', (channel_id,))

        row = cur.fetchone()

        if row:
            video_youngest = {
                'id': row[0],
                'published_at': row[1],
            }
            return video_youngest
        else:
            return None
    
    finally:
        conn.close()


def get_channel_ids(user_id, category_name=None, uncategorized=False):
    """Return user's channel IDs, optionally filtered by category or uncategorized state."""
    if category_name is not None and uncategorized:
        raise ValueError(f"Can't get {category_name} channels and uncategorized channels at the same time")
    
    conn = get_connection()
    cur = conn.cursor()

    try:
        if category_name is not None:
            cur.execute('''
                SELECT DISTINCT collections.channel_id
                FROM collections
                JOIN categories ON
                    categories.user_id = collections.user_id AND
                    collections.category_id = categories.id
                WHERE
                    collections.user_id = ? AND
                    categories.name = ?
            ''', (user_id, category_name))
        elif uncategorized:
            cur.execute('''
                SELECT DISTINCT subscriptions.channel_id
                FROM subscriptions
                LEFT JOIN collections ON
                    collections.user_id = subscriptions.user_id AND
                    collections.channel_id = subscriptions.channel_id
                WHERE
                    subscriptions.user_id = ? AND
                    collections.channel_id IS NULL
            ''', (user_id,))
        else:
            cur.execute('''
                SELECT DISTINCT channel_id
                FROM subscriptions
                WHERE user_id = ?
            ''', (user_id,))
    
        return [row[0] for row in cur.fetchall()]

    finally:
        conn.close()


def get_channel_ids_stale(channel_ids, freshness_hours=FRESHNESS_HOURS):
    """Return stale channel IDs from provided list."""
    if not channel_ids:
        return []

    # Convert to set to remove potential duplicates and speed up processing (original order not preserved)
    channel_ids = set(channel_ids)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f'''
        SELECT id, refreshed_at
        FROM channels
        WHERE id IN ({','.join('?' for _ in channel_ids)})
    ''', list(channel_ids))

    fresh_ids = set()
    for channel_id, refreshed_at in cur.fetchall():
        if refreshed_at and is_after_with_offset(refreshed_at, offset_hours=freshness_hours):
            fresh_ids.add(channel_id)
    
    conn.close()
    
    return channel_ids - fresh_ids


def get_channel_ids_unrefreshed(channel_ids):
    """Return unrefreshed channel IDs from provided list."""
    if not channel_ids:
        return []

    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(f'''
            SELECT id
            FROM channels
            WHERE
                id IN ({','.join('?' for _ in channel_ids)}) AND
                refreshed_at IS NULL
        ''', channel_ids)

        return set(row[0] for row in cur.fetchall())
        
    finally:
        conn.close()


def get_or_create_user(google_id, email):
    """Get user ID or create new user"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO users (google_id, email)
            VALUES (?, ?)
        ''', (google_id, email))
        user_id = cur.lastrowid
        conn.commit()
    
    except sqlite3.IntegrityError:
        conn.rollback()
        cur.execute('''
            SELECT id
            FROM users
            WHERE google_id = ?
        ''', (google_id,))
        user_id = cur.fetchone()[0]

    finally:
        conn.close()
        return user_id


def get_subscriptions_count(user_id):
    """Get current subscriptions count for user"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        SELECT COUNT(*)
        FROM subscriptions
        WHERE user_id = ?
    ''', (user_id,))

    count = cur.fetchone()[0]
    
    conn.close()

    return count


def get_subscriptions(user_id):
    """Get user's subscriptions' information + current category assignments"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT channels.id, channels.name, categories.name, subscriptions.subscribed_at, channels.refreshed_at
            FROM subscriptions
            JOIN channels ON
                channels.id = subscriptions.channel_id
            LEFT JOIN collections ON
                collections.user_id = subscriptions.user_id AND
                collections.channel_id = subscriptions.channel_id
            LEFT JOIN categories ON
                categories.user_id = subscriptions.user_id AND
                categories.id = collections.category_id
            WHERE
                subscriptions.user_id = ?
            ORDER BY channels.name COLLATE NOCASE
        ''', (user_id,))
        
        channels = []
        for row in cur.fetchall():
            channel = {
                'channel_id': row[0],
                'channel_name': row[1],
                'category_name': row[2],
                'subscribed_at': row[3],
                'subscribed_at_display': format_date(row[3]),
                'refreshed_at': row[4],
                'refreshed_at_display': format_date(row[4]),
                'is_fresh': is_after_with_offset(row[4], offset_hours=FRESHNESS_HOURS) if row[4] is not None else False,
            }
            channels.append(channel)
        
        return channels
    
    finally:
        conn.close()


def get_subscription_ids(user_id, cursor=None):
    conn = None
    if not cursor:
        conn = get_connection()
        cur = conn.cursor()
    else:
        cur = cursor
    
    try:
        cur.execute('''
            SELECT channel_id
            FROM subscriptions
            WHERE user_id = ?
        ''', (user_id,))

        subscription_ids = []
        for row in cur.fetchall():
            subscription_ids.append(row[0])
        
        return subscription_ids
    
    finally:
        if conn:
            conn.close()


def get_subscriptions_differences(user_id, channels):
    existing_subscription_ids = set(get_subscription_ids(user_id))

    fetched_channels_by_id = {
        channel['channel_id']: channel for channel in channels
    }
    fetched_subscription_ids = set(fetched_channels_by_id.keys())

    channel_ids_to_add = list(fetched_subscription_ids - existing_subscription_ids)
    channel_ids_to_remove = list(existing_subscription_ids - fetched_subscription_ids)

    return {
        'channels_to_add': [
            fetched_channels_by_id[channel_id] for channel_id in channel_ids_to_add
        ],
        'channel_ids_to_add': channel_ids_to_add,
        'channel_ids_to_remove': channel_ids_to_remove,
    }


def get_used_category_names(user_id):
    """Get user's category names that are assigned to at least one channel"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        SELECT DISTINCT categories.name
        FROM categories
        JOIN collections ON
            collections.user_id = categories.user_id AND
            collections.category_id = categories.id
        WHERE
            categories.user_id = ?
        ORDER BY
            categories.name ASC
    ''', (user_id,))

    category_names = []
    for row in cur.fetchall():
        category_names.append(row[0])
    
    conn.close()

    return category_names


def get_videos_from_channel(channel_id, cursor=None, after_published_at=None, after_id=None, short_duration_seconds=150):
    """
    Get cached non-short video candidates for channel.
    Use existing connection cursor if provided, otherwise open new connection.
    """

    if (after_published_at is None) != (after_id is None):
        raise ValueError("after_published_at and after_id must be provided together")

    if not channel_id or short_duration_seconds <= 0:
        return []
    
    conn = None
    if not cursor:
        conn = get_connection()
        cur = conn.cursor()
    else:
        cur = cursor

    try:
        where_clause = f'''
            videos.channel_id = ? AND
            (videos.duration_seconds >= ? OR videos.duration_seconds = 0 OR videos.duration_seconds IS NULL)
        '''
        params = [channel_id, short_duration_seconds]

        if after_published_at is not None and after_id is not None:
            where_clause += '''
                AND
                (videos.published_at < ? OR
                (videos.published_at = ? AND videos.id < ?))
            '''
            params.extend([after_published_at, after_published_at, after_id])

        cur.execute(f'''
            SELECT
                videos.id, videos.title, videos.published_at, videos.thumbnail_url, videos.duration_seconds, videos.refreshed_at, 
                channels.name, channels.id
            FROM videos
            JOIN channels ON channels.id = videos.channel_id
            WHERE {where_clause}
            ORDER BY
                videos.published_at DESC,
                videos.id DESC
        ''', params)

        videos = []
        for row in cur.fetchall():
            videos.append({
                'id': row[0],
                'title': row[1],
                'published_at': row[2],
                'published_at_display': format_date(row[2]),
                'thumbnail_url': row[3],
                'duration_display': format_seconds(row[4]),
                'refreshed_at': row[5],
                'channel_name': row[6],
                'channel_id': row[7],
            })

        return videos

    finally:
        if conn:
            conn.close()


def get_videos_from_channels(channel_ids, after_published_at=None, after_id=None, short_duration_seconds=150):
    """Get cached non-short video candidates for list of channels"""
    if (after_published_at is None) != (after_id is None):
        raise ValueError("after_published_at and after_id must be provided together")

    if not channel_ids or short_duration_seconds <= 0:
        return []
    
    conn = get_connection()
    cur = conn.cursor()

    try:
        videos = []
        for channel_id in channel_ids:
            videos.extend(get_videos_from_channel(channel_id, cursor=cur, after_published_at=after_published_at, after_id=after_id))
        
        videos.sort(key=lambda v: (v["published_at"], v["id"]), reverse=True)
        return videos

    finally:
        conn.close()


def get_video_ids_missing_durations(channel_ids, max_videos=50):
    """Get up to max_videos most recent cached videos missing duration for given channels"""
    if not channel_ids or max_videos <= 0:
        return []
    
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(f'''
            SELECT id
            FROM videos
            WHERE
                channel_id IN ({",".join("?" for _ in channel_ids)}) AND
                duration_seconds IS NULL
            ORDER BY published_at DESC
            LIMIT ?
        ''', (*channel_ids, max_videos))

        return [row[0] for row in cur.fetchall()]

    finally:
        conn.close()


def refresh_channel(channel_id, channel_name, next_page_token, refreshed_at=None):
    """Update channel after querying channel's uploads playlist"""
    if not channel_id:
        return
    
    if refreshed_at is None:
        refreshed_at = datetime.now(timezone.utc).isoformat()
    
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()

        if channel_name:
            name_old = get_channel_name(channel_id, cur)
            if name_old and channel_name.strip() != name_old.strip():
                print(f"ℹ️ refresh_channel: channel name changed: {name_old} -> {channel_name}")

            query_string = '''
                UPDATE channels
                SET name = ?, backfill_complete = ?, next_page_token = ?, refreshed_at = ?
                WHERE id = ?
            '''
            params = [channel_name, 0 if next_page_token else 1, next_page_token, refreshed_at, channel_id]
        
        else:
            query_string = '''
                UPDATE channels
                SET backfill_complete = ?, next_page_token = ?, refreshed_at = ?
                WHERE id = ?
            '''
            params = [0 if next_page_token else 1, next_page_token, refreshed_at, channel_id]

        cur.execute(query_string, params)
        conn.commit()
    
    except Exception as e:
        conn.rollback()
        print(f"❌ refresh_channel failed: {e}")
        raise

    finally:
        conn.close()


def rename_category(user_id, category_id, category_name):
    """Rename a category for user"""
    if category_name is not None:
        category_name = category_name.strip()
    
    if not user_id or not category_id or not category_name:
        return False
    
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()
    
        # Check if category exists for this user
        cur.execute('''
            SELECT name
            FROM categories
            WHERE
                id = ? AND
                user_id = ?
        ''', (category_id, user_id))
        category = cur.fetchone()
        if not category:
            return False
        
        category_name_old = category[0]

        # Check if new name is same as existing name
        if category_name == category_name_old:
            return False
        
        # Check if category name exists for another category for this user
        cur.execute('''
            SELECT 1
            FROM categories
            WHERE
                name = ? AND
                user_id = ? AND
                id != ?
        ''', (category_name, user_id, category_id))
        if cur.fetchone():
            return False
        
        # Rename category for this user
        cur.execute('''
            UPDATE categories
            SET name = ?
            WHERE
                id = ? AND
                user_id = ?
        ''', (category_name, category_id, user_id))
        
        conn.commit()
        return True
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to rename category {category_id} to {category_name}: {e}")
        raise

    finally:
        conn.close()


def save_subscription(user_id, subscription):
    """Save channel + subscription"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    
    try:
        cur = conn.cursor()

        # Add channel to channels table for all users
        cur.execute('''
            INSERT INTO channels (id, name)
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name
        ''', (subscription['channel_id'], subscription['channel_name']))

        # Add subscription to subscriptions table for user
        cur.execute('''
            INSERT INTO subscriptions (user_id, channel_id, subscribed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, channel_id) DO UPDATE SET subscribed_at = excluded.subscribed_at
        ''', (user_id, subscription['channel_id'], subscription['subscribed_at']))

        conn.commit()

        print(
            f"✅ save_subscription: saved channel {subscription['channel_name']} ({subscription['channel_id']}) "
            f"subscribed at {subscription['subscribed_at']} for user {user_id}"
        )

        return True
    
    except Exception as e:
        conn.rollback()

        print(
            f"❌ save_subscription: failed to save channel {subscription['channel_name']} ({subscription['channel_id']}) "
            f"for user {user_id}: {e}"
        )

        return False

    finally:
        conn.close()


def save_subscriptions(user_id, subscriptions):
    success_count = 0

    for sub in subscriptions:
        if save_subscription(user_id, sub):
            success_count += 1
    
    print(f"ℹ️ save_subscriptions: {success_count}/{len(subscriptions)} subscriptions added for user {user_id}")

    return success_count


def save_subscriptions_bulk(user_id, subscriptions):
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    
    try:
        cur = conn.cursor()
        
        # Add all channels to channels table for all users
        channel_rows = []
        for sub in subscriptions:
            channel_rows.append({
                'channel_id': sub['channel_id'],
                'channel_name': sub['channel_name'],
            })
        
        cur.executemany('''
            INSERT INTO channels (id, name)
            VALUES (:channel_id, :channel_name)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name
        ''', channel_rows)

        # Add all subscriptions to subscriptions table for user
        subscription_rows = [
            {
                'user_id': user_id,
                'channel_id': sub['channel_id'],
                'subscribed_at': sub['subscribed_at'],
            }
            for sub in subscriptions
        ]

        cur.executemany('''
            INSERT INTO subscriptions (user_id, channel_id, subscribed_at)
            VALUES (:user_id, :channel_id, :subscribed_at)
            ON CONFLICT(user_id, channel_id) DO UPDATE SET subscribed_at = excluded.subscribed_at
        ''', subscription_rows)

        conn.commit()

        print(f"✅ save_subscriptions_bulk saved {len(subscriptions)} channels for user {user_id}")

        return True
    
    except Exception as e:
        conn.rollback()

        print(f"❌ save_subscriptions_bulk failed to save subscriptions for user {user_id}: {e}")

        return False
    
    finally:
        conn.close()


def save_videos(fetched_videos):
    """Save videos fetched from playlistItems"""
    if not fetched_videos:
        return {
            'success': True,
            'old_count': 0,
            'fetched_count': 0,
            'new_count': 0,
        }

    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()

        video_ids = [video['id'] for video in fetched_videos]

        cur.execute(f'''
            SELECT COUNT(*)
            FROM videos
            WHERE id IN ({','.join('?' for _ in video_ids)})
        ''', video_ids)

        old_count = cur.fetchone()[0]
        fetched_count = len(fetched_videos)
        new_count = fetched_count - old_count

        cur.executemany('''
            INSERT INTO videos (id, title, published_at, thumbnail_url, channel_id)
            VALUES (:id, :title, :published_at, :thumbnail_url, :channel_id)
            ON CONFLICT(id) DO UPDATE SET
                title = COALESCE(excluded.title, videos.title),
                published_at = COALESCE(excluded.published_at, videos.published_at),
                thumbnail_url = COALESCE(excluded.thumbnail_url, videos.thumbnail_url),
                channel_id = COALESCE(excluded.channel_id, videos.channel_id)
        ''', fetched_videos)

        conn.commit()

        return {
            'success': True,
            'old_count': old_count,
            'fetched_count': fetched_count,
            'new_count': new_count,
        }

    except Exception as e:
        conn.rollback()

        print(f"❌ save_videos failed: {e}")

        raise

    finally:
        conn.close()


def unsubscribe_channel(user_id, channel_id):
    """Remove channel from user's collections and subscriptions tables."""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    
    try:
        cur = conn.cursor()

        # Remove channel from user's collections table
        cur.execute('''
            DELETE FROM collections
            WHERE user_id = ? AND channel_id = ?
        ''', (user_id, channel_id))

        # Remove channel from user's subscriptions table
        cur.execute('''
            DELETE FROM subscriptions
            WHERE user_id = ? AND channel_id = ?
        ''',(user_id, channel_id))

        conn.commit()

        print(
            f"✅ unsubscribe_channel: removed channel {get_channel_name(channel_id, cur)} ({channel_id}) "
            f"from collections and subscriptions for user {user_id}"
        )

        return True
    
    except Exception as e:
        conn.rollback()

        print(
            f"❌ unsubscribe_channel: failed to remove channel {get_channel_name(channel_id, cur)} ({channel_id}) "
            f"for user {user_id}: {e}"
        )

        return False

    finally:
        conn.close()


def unsubscribe_channels(user_id, channel_ids):
    """Remove channels from user's collections and subscriptions tables."""
    success_count = 0

    for channel_id in channel_ids:
        if unsubscribe_channel(user_id, channel_id):
            success_count += 1
    
    print(
        f"ℹ️ unsubscribe_channels: {success_count}/{len(channel_ids)} channels removed from collections and subscriptions "
        f"for user {user_id}"
    )

    return success_count


# UNUSED but kept as a future reference of an efficient batch delete implementation
def unsubscribe_channels_bulk(user_id, channel_ids):
    """Remove channels from user's  collections and subscriptions tables."""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")
    
    try:
        cur = conn.cursor()
        
        delete_rows = [(user_id, channel_id) for channel_id in channel_ids]

        # Remove channels from user's collections table
        cur.executemany('''
            DELETE FROM collections
            WHERE user_id = ? AND channel_id = ?
        ''', delete_rows)

        # Remove channels from user's subscriptions table
        cur.executemany('''
            DELETE FROM subscriptions
            WHERE user_id = ? AND channel_id = ?
        ''', delete_rows)

        conn.commit()

        print(
            f"✅ unsubscribe_channels_bulk removed {len(channel_ids)} channels "
            f"from collections and subscriptions for user {user_id}"
        )

        return True
    
    except Exception as e:
        conn.rollback()

        print(f"❌ unsubscribe_channels_bulk failed to remove subscriptions for user {user_id}: {e}")

        return False
    
    finally:
        conn.close()


def update_channel_assignment(user_id, channel_id, category_id=None):
    """Update channel's category assignment"""
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()

        # Remove any existing assignment
        cur.execute('''
            DELETE FROM collections
            WHERE
                channel_id = ? AND
                user_id = ?
        ''', (channel_id, user_id))

        # If a category selected, add new assignment
        if category_id:
            cur.execute('''
                SELECT 1
                FROM categories
                WHERE id = ? AND user_id = ?
            ''', (category_id, user_id))

            if cur.fetchone() is not None:
                cur.execute('''
                    INSERT INTO collections (user_id, channel_id, category_id)
                    VALUES (?, ?, ?)
                ''', (user_id, channel_id, category_id))

        conn.commit()
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Update assignment failed: {e}")
        raise

    finally:
        conn.close()


def update_videos(fetched_videos):
    """Update video durations and other optional metadata"""
    if not fetched_videos:
        return True
    
    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()
        cur.executemany('''
            UPDATE videos
            SET
                title = COALESCE(:title, title),
                published_at = COALESCE(:published_at, published_at),
                refreshed_at = COALESCE(:refreshed_at, refreshed_at),
                thumbnail_url = COALESCE(:thumbnail_url, thumbnail_url),
                duration_seconds = COALESCE(:duration_seconds, duration_seconds)
            WHERE id = :id
        ''', fetched_videos)
        conn.commit()
        return True
    
    except Exception as e:
        conn.rollback()
        print(f"❌ update_videos failed: {e}")
        raise

    finally:
        conn.close()


def reset_video_durations(freshness_hours=FRESHNESS_HOURS):
    """Reset video durations and refreshed_at for live streams"""

    conn = get_connection()
    conn.execute("BEGIN TRANSACTION")

    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE videos
            SET
                refreshed_at = NULL,
                duration_seconds = NULL
            WHERE 
                duration_seconds = 0 AND 
                refreshed_at < ?
        ''', (
            (datetime.now(timezone.utc) - timedelta(hours=freshness_hours)).isoformat(),
        ))
        conn.commit()
    
    except Exception as e:
        conn.rollback()
        print(f"❌ reset_video_durations failed: {e}")
        raise

    finally:
        conn.close()