from database import (
    get_channel_depth_info,
    get_channels_depth_info,
    get_channel_name,
    get_channel_ids,
    get_channel_ids_stale,
    get_channel_ids_unrefreshed,
    get_channel_next_page_token,
    get_channel_video_youngest,
    get_videos_from_channels,
    get_video_ids_missing_durations,
    refresh_channel,
    reset_video_durations,
    save_videos,
    update_videos,
)
from datetime import (
    datetime,
    timezone,
)
from helpers import (
    chunked,
    parse_duration_to_seconds,
)
import json, requests

CLIENT_SECRETS_FILE = 'client_secret.json'
PAGE_SIZE = 18
FRESHNESS_HOURS = 12

def load_api_key():
    """Load YouTube API key from client_secret.json"""
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        creds = json.load(f)
    client_config = creds.get('web') or creds.get('installed')
    return client_config['youtube_api_key']

API_KEY = load_api_key()


def load_google_credentials():
    """Load OAuth credentials from client_secret.json"""
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        creds = json.load(f)
    
    client_config = creds.get('web') or creds.get('installed')
    return client_config['client_id'], client_config['client_secret']


def fetch_subscriptions(access_token):
    """Fetch user's YouTube subscriptions"""
    url = "https://www.googleapis.com/youtube/v3/subscriptions"
    params = {
        'part': 'snippet',
        'fields': 'items(snippet(resourceId/channelId,title,publishedAt)),nextPageToken',
        'mine': 'true',
        'maxResults': 50,
        'access_token': access_token
    }

    fetched_subs = []
    next_page = None

    while True:
        if next_page:
            params['pageToken'] = next_page
        
        response = requests.get(url, params=params)
        data = response.json()

        if 'error' in data:
            print(f"❌ fetch_subscriptions YouTube API Error: {data['error']}")
            return None
            
        if 'items' not in data:
            print(f"❌ fetch_subscriptions no 'items' in response: {list(data.keys())}")
            return []

        print(f"✅ Got {len(data['items'])} subscriptions (running total: {len(fetched_subs)})")

        for item in data['items']:
            fetched_subs.append({
                'channel_id': item['snippet']['resourceId']['channelId'], 
                'channel_name': item['snippet'].get('channelTitle') or item['snippet'].get('title'),
                'subscribed_at': item['snippet'].get('publishedAt'),
            })

        next_page = data.get('nextPageToken')
        if not next_page:
            break

    return fetched_subs


# UNUSED but kept as a valid fallback / alternative strategy
def fetch_uploads_playlist(channel_id):
    """Get channel's uploads playlist ID"""
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        'part': 'contentDetails',
        'id': channel_id,
        'key': API_KEY
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if 'items' in data and data['items']:
        return data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    else:
        return None


def fetch_video_data(video_ids):
    """Fetch video duration and other optional metadata for existing cached videos"""
    if not video_ids:
        return []

    videos = []

    url = "https://www.googleapis.com/youtube/v3/videos"
    # Chunk video IDs into groups of 50 for videos.list API limit
    for batch in chunked(video_ids, 50):
        params = {
            'part': 'contentDetails,snippet',
            'fields': 'items(id,snippet(title,publishedAt,thumbnails/medium/url),contentDetails/duration)',
            'id': ','.join(batch),
            'key': API_KEY
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if 'error' in data:
                print(f"❌ fetch_video_data batch error: {data['error']}")
                continue

            if 'items' not in data:
                print(f"❌ fetch_video_data batch error: no 'items' in videos response")
                continue
            
            refreshed_at = datetime.now(timezone.utc).isoformat()

            for item in data.get('items', []):
                try:
                    videos.append({
                        'id': item['id'],
                        'title': item.get('snippet', {}).get('title'),
                        'published_at': item.get('snippet', {}).get('publishedAt'),
                        'refreshed_at': refreshed_at,
                        'thumbnail_url': item.get('snippet', {}).get('thumbnails', {}).get('medium', {}).get('url'),
                        'duration_seconds': parse_duration_to_seconds(item['contentDetails']['duration'])
                    })
            
                except Exception as e:
                    print(
                        (f"⚠️ fetch_video_data skipped video: {e}\n", 
                        {
                            'id': item.get('id'), 
                            'title': item.get('snippet', {}).get('title'), 
                            'published_at': item.get('snippet', {}).get('publishedAt'), 
                        })
                    )
                    continue

            print(
                "ℹ️ fetch_video_data non-shorts: "
                f"{sum(1 for v in videos if v['duration_seconds'] is not None and v['duration_seconds'] >= 150)}"
                "/"
                f"{len(videos)}"
            )
        
        except Exception as e:
            print(f"❌ fetch_video_data batch error: {e}")
            continue

    return videos


def fetch_uploads(channel_id, next_page_token=None):
    """Fetch videos from channel's uploads playlist"""
    url = "https://www.googleapis.com/youtube/v3/playlistItems"

    params = {
        'part': 'contentDetails,snippet',
        'fields': (
            'items(contentDetails(videoPublishedAt),'
            'snippet(channelTitle,resourceId(kind,videoId),title,thumbnails/medium/url)),'
            'nextPageToken'
        ),
        'playlistId': f"UU{channel_id[2:]}",
        'maxResults': 50,
        'key': API_KEY
    }

    if next_page_token:
        params['pageToken'] = next_page_token
    
    fetched_uploads = []

    try:
        response = requests.get(url, params=params)
        data = response.json()

        error_printout = None
        if 'error' in data:
            error_printout = f"❌ fetch_uploads playlistItems API error for {get_channel_name(channel_id)}: {data['error']}"
        elif 'items' not in data:
            error_printout = f"❌ fetch_uploads: no 'items' in playlistItems response for {get_channel_name(channel_id)}"
        
        items = data.get('items', [])

        if not error_printout and len(items) == 0:
            error_printout = f"❌ fetch_uploads: length of 'items' in playlistItems is zero for {get_channel_name(channel_id)}"

        if error_printout:
            print(error_printout)
            return {
                'fetched_uploads': fetched_uploads,
                'next_page_token': None,
                'channel_name': None,
                'success': False,
            }

        print(f"✅ {len(items)} playlist items fetched for channel {get_channel_name(channel_id)}")
        
        for item in items:
            try:
                if item['snippet']['resourceId']['kind'] != "youtube#video":
                    continue

                fetched_uploads.append({
                    'id': item['snippet']['resourceId']['videoId'],
                    'title': item['snippet'].get('title'),
                    'thumbnail_url': item['snippet'].get('thumbnails', {}).get('medium', {}).get('url'),
                    'published_at': item['contentDetails']['videoPublishedAt'],
                    'channel_id': channel_id,
                })
        
            except Exception as e:
                print(f"⚠️ fetch_uploads: channel {get_channel_name(channel_id)} playlist item skipped: {e}")
                continue

        channel_name = None
        for item in items:
            channel_name = item['snippet'].get('channelTitle')
            if channel_name:
                break
        
        return {
            'fetched_uploads': fetched_uploads,
            'next_page_token': data.get('nextPageToken'),
            'channel_name': channel_name,
            'success': True,
        }

    except Exception as e:
        print(f"❌ Channel {get_channel_name(channel_id)} error: {e}")
        return {
            'fetched_uploads': fetched_uploads,
            'next_page_token': None,
            'channel_name': None,
            'success': False,
        }


def fetch_videos(
    user_id,
    category_name=None,
    uncategorized=False,
    after_published_at=None,
    after_id=None,
    page_size=PAGE_SIZE,
):
    """Get videos for page display"""

    # Get channel IDs for current page filters
    channel_ids = get_channel_ids(user_id, category_name=category_name, uncategorized=uncategorized)
    if not channel_ids:
        print("❌ fetch_videos: no channels")
        return {
            'videos': [],
            'last_cursor': None,
            'has_more': False,
        }

    # Check for channels that had never been refreshed before loading page 1 and fetch recent videos for those channels
    if after_published_at is None and after_id is None:
        channel_ids_unrefreshed = get_channel_ids_unrefreshed(channel_ids)
        if channel_ids_unrefreshed:
            refresh_channels(channel_ids_unrefreshed, ignore_freshness=True, reset_pagination=True)

    MAX_DEPTH_ITERATIONS = 5
    for depth_iteration in range(MAX_DEPTH_ITERATIONS):
        print(f"ℹ️ fetch_videos: depth_iteration {depth_iteration}")

        # Get most recent non-short videos from database
        reset_video_durations()
        video_candidates = get_videos_from_channels(channel_ids, after_published_at=after_published_at, after_id=after_id)

        # Fetch missing durations if necessary
        page_candidates = video_candidates[:page_size]
        missing_duration_count = sum(1 for video in page_candidates if video['duration_display'] is None)

        if missing_duration_count > 0:
            print(f"ℹ️ fetch_videos: {missing_duration_count}/{len(page_candidates)} videos are missing duration")
            video_ids_to_fetch = get_video_ids_missing_durations(channel_ids)
            fetched_videos_to_refresh = fetch_video_data(video_ids_to_fetch)
            if fetched_videos_to_refresh:
                update_success = update_videos(fetched_videos_to_refresh)
                if update_success:
                    video_candidates = get_videos_from_channels(
                        channel_ids, 
                        after_published_at=after_published_at, 
                        after_id=after_id
                    )

        # Exclude videos with unresolved durations
        videos_to_serve = []
        last_cursor = None
        has_more = False

        for video in video_candidates:
            if video['duration_display'] is None:
                continue

            videos_to_serve.append(video)

            # Save last video served cursor
            if len(videos_to_serve) <= page_size:
                last_cursor = {
                    'after_published_at': video['published_at'],
                    'after_id': video['id'],
                }
            
            # Find out if there is a video to serve after cursor
            if len(videos_to_serve) > page_size:
                has_more = True
                break
        
        print(
            "ℹ️ fetch_videos:",
            {
                'videos_to_serve': len(videos_to_serve),
                'page_boundary': last_cursor['after_published_at'] if last_cursor else None,
            }
        )

        # Check if any channel's history does not go back far enough and fetch more videos if needed
        channels_depth_info = get_channels_depth_info(channel_ids)
        channel_ids_to_fetch_more = []

        for channel in channels_depth_info:
            if channel['backfill_complete'] == 0 and \
            (
                not has_more or 
                last_cursor is None or 
                channel['published_at_oldest'] is None or 
                (channel['published_at_oldest'], channel['published_at_oldest_id']) > \
                (last_cursor['after_published_at'], last_cursor['after_id'])
            ):
                channel_ids_to_fetch_more.append(channel['channel_id'])
                print(
                    (f"ℹ️ fetch_videos: playlistItems backfill fetch required for channel '{channel['channel_name']}'\n"
                    f"{channel['published_at_oldest']} oldest stored video\n"
                    f"{last_cursor['after_published_at'] if last_cursor else None} page boundary")
                )

        if not channel_ids_to_fetch_more:
            break

        refresh_channels(channel_ids_to_fetch_more, ignore_freshness=True, reset_pagination=False)

    return {
        'videos': videos_to_serve[:page_size],
        'last_cursor': last_cursor if has_more else None,
        'has_more': has_more, 
    }


def refresh_channels(channel_ids, ignore_freshness=False, reset_pagination=False, freshness_hours=FRESHNESS_HOURS):
    requested_count = len(channel_ids)

    # If background refresh, only query stale channels to limit quota usage
    if not ignore_freshness:
        channel_ids = get_channel_ids_stale(channel_ids, freshness_hours=freshness_hours)

    filtered_count = len(channel_ids)
    attempted_count = 0
    success_count = 0
    failure_count = 0

    # Fetch recent uploads for channels and save them to database
    refreshed_at = datetime.now(timezone.utc).isoformat()
    for channel_id in channel_ids:
        attempted_count += 1

        video_youngest = get_channel_video_youngest(channel_id)
        oldest_before = get_channel_depth_info(channel_id)

        fetch_uploads_result = fetch_uploads(channel_id, None if reset_pagination else get_channel_next_page_token(channel_id))
        fetched_uploads = fetch_uploads_result['fetched_uploads']
        save_result = save_videos(fetched_uploads)

        if fetch_uploads_result['success'] and save_result['success']:
            if save_result['new_count'] == 0:
                print(f"⚠️ refresh_channels: no new videos saved for channel {get_channel_name(channel_id)}")
            else:
                print(
                    f"ℹ️ refresh_channels: "
                    f"{save_result['new_count']}/{save_result['fetched_count']} videos were new "
                    f"for channel {get_channel_name(channel_id)}"
                )

            oldest_after = get_channel_depth_info(channel_id)
            print(
                f"ℹ️ refresh_channels: channel {get_channel_name(channel_id)} oldest video "
                f"{oldest_before['published_at_oldest']} -> {oldest_after['published_at_oldest']}"
            )

            # Do not update stored next page token if no videos were fetched \
            # or if most recent fetched videos overlap with database
            if not fetched_uploads or \
            (
                reset_pagination 
                and 
                video_youngest 
                and 
                (video_youngest['published_at'], video_youngest['id']) >= \
                (fetched_uploads[-1]['published_at'], fetched_uploads[-1]['id'])
            ):
                next_page_token = get_channel_next_page_token(channel_id)
            else:
                next_page_token = fetch_uploads_result['next_page_token']

            # Refresh channels table in database
            refresh_channel(channel_id, fetch_uploads_result['channel_name'], next_page_token, refreshed_at)

            success_count += 1
        else:
            failure_count += 1

    return {
        'ignore_freshness': ignore_freshness,
        'requested_count': requested_count,
        'filtered_count': filtered_count,
        'attempted_count': attempted_count,
        'success_count': success_count,
        'failure_count': failure_count,
    }