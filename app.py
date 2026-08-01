from authlib.integrations.flask_client import OAuth
from database import (
    assign_category_to_channel,
    create_category,
    delete_category,
    get_categories,
    get_channel_ids,
    get_channel_names,
    get_or_create_user,
    get_subscriptions,
    get_subscriptions_count,
    get_subscriptions_differences,
    get_used_category_names,
    init_db,
    rename_category,
    save_subscriptions,
    save_subscriptions_bulk,
    unsubscribe_channels,
    update_channel_assignment,
)
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from helpers import (
    normalize_string_start,
    parse_sort_param,
)
from youtube_api import (
    fetch_videos,
    fetch_subscriptions,
    load_google_credentials,
    refresh_channels,
)
import json, os, requests, time

CLIENT_SECRETS_FILE = 'client_secret.json'


app = Flask(__name__)
# app.secret_key = os.urandom(24)

def load_flask_secret_key():
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        creds = json.load(f)
    client_config = creds.get('web') or creds.get('installed')
    return client_config['flask_secret_key']

app.secret_key = load_flask_secret_key()


oauth = OAuth(app)

CLIENT_ID, CLIENT_SECRET = load_google_credentials()

oauth.register(
    name='google',
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/youtube.readonly'
    }
)


def unauthorized_api_response():
    return jsonify(error='unauthorized', login_url=url_for('google_login')), 401


@app.route('/')
@app.route('/subscriptions')
def index():
    if 'user_id' not in session:
        return redirect(url_for('google_login'))
    
    user_id = session['user_id']
    category_name, uncategorized = get_video_filters()
    page_data = fetch_videos(
        user_id,
        category_name=category_name,
        uncategorized=uncategorized,
    )

    return render_template (
        'subscriptions.html',
        videos=page_data["videos"],
        category_name=category_name,
        uncategorized=uncategorized,
        last_cursor=page_data['last_cursor'],
        has_more=page_data['has_more'],
        used_category_names=get_used_category_names(user_id),
        nav_menu_mode='refresh',
    )


@app.route('/subscriptions/load-more')
def load_more_videos():
    if 'user_id' not in session:
        return unauthorized_api_response()
    
    user_id = session['user_id']
    category_name, uncategorized = get_video_filters()
    page_data = fetch_videos(
        user_id,
        category_name=category_name,
        uncategorized=uncategorized,
        after_published_at = request.args.get("after_published_at"),
        after_id = request.args.get("after_id"),
    )

    return jsonify(
        videos=page_data["videos"],
        last_cursor=page_data["last_cursor"],
        has_more=page_data["has_more"],
    )


@app.route('/subscriptions/refresh', methods=['POST'])
def refresh_subscriptions():
    if 'user_id' not in session:
        return unauthorized_api_response()
    
    user_id = session['user_id']
    category_name, uncategorized = get_video_filters()
    channel_ids = get_channel_ids(user_id, category_name=category_name, uncategorized=uncategorized)
    result = refresh_channels(channel_ids, ignore_freshness=True, reset_pagination=True)

    return jsonify(success=True, result=result)


def get_video_filters():
    source = request.form if request.method == "POST" else request.args
    category_name = (source.get("category") or "").strip() or None
    uncategorized = False if category_name else source.get("uncategorized") == "1"
    return category_name, uncategorized


@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('google_login'))
    
    user_id = session['user_id']
    
    # Get channels, categories and current assignments
    channels = get_subscriptions(user_id)
    categories = get_categories(user_id)

    # Get sort parameters from URL
    sort_param = request.args.get("sort")
    sort_criteria = parse_sort_param(sort_param) if sort_param else []

    # Create sort dictionary for HTML
    sort_directions = {
        criterion['field']: criterion['direction']
        for criterion in sort_criteria
    }

    # Set primary sort parameters for aria-sort
    primary_sort_field = None
    primary_sort_direction = None

    if sort_criteria:
        primary_sort_field = sort_criteria[0]['field']
        primary_sort_direction = ("descending" if sort_criteria[0]['direction'] == "desc" else "ascending")

    # Enable default sort rule for channel name if it's not actively sorted
    if not any(c['field'] == "channel_name" for c in sort_criteria):
        sort_criteria.append({
            'field': "channel_name",
            'direction': "asc",
        })

    # Sort columns from sort parameters (right-to-left for lowest-to-highest priority)
    for sort_criterion in reversed(sort_criteria):
        field = sort_criterion['field']
        reverse = sort_criterion['direction'] == "desc"

        # Empty text values go to the bottom in an ascending sort
        if field in ("channel_name", "category_name"):
            channels = sorted(
                channels,
                key=lambda channel: (not channel[field], normalize_string_start(channel[field] or "")),
                reverse=reverse,
            )
        # Empty date values (smallest, equivalent to never) go the bottom in a descending sort
        else:
            channels = sorted(
                channels,
                key=lambda channel: (bool(channel[field]), channel[field] or ""),
                reverse=reverse,
            )

    # Get list of used category names to be displayed in navigation bar
    used_category_names = get_used_category_names(user_id)
    
    return render_template(
        'admin.html',
        channels=channels,
        categories=categories,
        used_category_names=used_category_names,
        user_id=user_id,
        nav_menu_mode='actions',
        sort_directions=sort_directions,
        primary_sort_field=primary_sort_field,
        primary_sort_direction=primary_sort_direction,
    )


@app.route('/admin/assign', methods=['POST'])
def admin_assign():
    if 'user_id' not in session:
        return unauthorized_api_response()
    
    user_id = session['user_id']
    channel_id = request.form['channel_id']
    category_id = request.form['category_id']
    
    assign_category_to_channel(user_id, channel_id, category_id)
    return redirect(url_for('admin'))


@app.route('/admin/create-category', methods=['POST'])
def admin_create_category():
    if 'user_id' not in session:
        return unauthorized_api_response()

    user_id = session['user_id']
    category_name = request.form['category_name'].strip()

    if not category_name:
        return jsonify(
            success=False,
            message="empty_name",
            category_name="",
        )

    result = create_category(category_name, user_id)
    if result == 'EXISTS':
        return jsonify(
            success=False,
            message="exists",
            category_name=category_name,
        )
    else:
        return jsonify(
            success=True,
            message="created",
            category_name=category_name,
        )


@app.route('/admin/delete-category', methods=['POST'])
def admin_delete_category():
    if 'user_id' not in session:
        return unauthorized_api_response()

    user_id = session['user_id']
    category_id = request.form['category_id']

    success = delete_category(category_id, user_id)
    return jsonify(success=success), 200 if success else 404


@app.route('/admin/rename-category', methods=['POST'])
def admin_rename_category():
    if 'user_id' not in session:
        return unauthorized_api_response()

    user_id = session['user_id']
    category_id = request.form['category_id']
    category_name = request.form['category_name']

    success = rename_category(user_id, category_id, category_name)
    return jsonify(success=success), 200 if success else 404


@app.route('/admin/update-assignment', methods=['POST'])
def admin_update_assignment():
    if 'user_id' not in session:
        return unauthorized_api_response()

    user_id = session['user_id']
    channel_id = request.form['channel_id']
    category_id = request.form['category_id'] or None

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        category_id = None

    update_channel_assignment(user_id, channel_id, category_id)
    return "", 204  # No‑content; successful update


@app.route('/admin/update-subscriptions', methods=['POST'])
def admin_update_subscriptions():
    if 'user_id' not in session or 'access_token' not in session:
        return unauthorized_api_response()

    user_id = session['user_id']
    access_token = session['access_token']

    error_return = jsonify(
        success=False,
        confirmation_needed=False,
        add_names=[],
        remove_names=[],
        total_count=0,
    )

    try:
        confirmed_unsubscribe = request.get_json(silent=True) or {}
        confirmed_unsubscribe = confirmed_unsubscribe.get('confirmed_unsubscribe', False)

        if confirmed_unsubscribe:
            if 'pending_subscriptions_update' in session \
            and int(time.time()) <= session['pending_subscriptions_update']['expires_at']:
                channels_to_add = session['pending_subscriptions_update']['channels_to_add']
                channel_ids_to_remove = session['pending_subscriptions_update']['channel_ids_to_remove']
                add_names = session['pending_subscriptions_update']['add_names']
                remove_names = session['pending_subscriptions_update']['remove_names']
            else:
                confirmed_unsubscribe = False
            
        session.pop('pending_subscriptions_update', None)

        if not confirmed_unsubscribe:
            fetched_subscriptions = fetch_subscriptions(access_token)
            if fetched_subscriptions is None:
                return error_return, 500

            subscriptions_differences = get_subscriptions_differences(user_id, fetched_subscriptions)

            channels_to_add = subscriptions_differences['channels_to_add']
            channel_ids_to_remove = subscriptions_differences['channel_ids_to_remove']
            add_names = [channel['channel_name'] for channel in subscriptions_differences['channels_to_add']]
            remove_names = get_channel_names(subscriptions_differences['channel_ids_to_remove'])

            session['pending_subscriptions_update'] = {
                'channels_to_add': subscriptions_differences['channels_to_add'],
                'channel_ids_to_remove': subscriptions_differences['channel_ids_to_remove'],
                'add_names': add_names,
                'remove_names': remove_names,
                'expires_at': int(time.time()) + 60*5,
            }

        if len(channel_ids_to_remove) > 0 and confirmed_unsubscribe == False:
            return jsonify(
                success=False,
                confirmation_needed=True,
                add_names=add_names,
                remove_names=remove_names,
                total_count=0,
            )

        unsubscribed_count = 0
        if len(channel_ids_to_remove) > 0 and confirmed_unsubscribe == True:
            unsubscribed_count = unsubscribe_channels(user_id, channel_ids_to_remove)

        added_count = 0
        if len(channels_to_add) > 0:
            added_count = save_subscriptions(user_id, channels_to_add)
        
        if (
            (
                (len(channel_ids_to_remove) > 0 and unsubscribed_count > 0) 
                or len(channel_ids_to_remove) == 0
            ) and (
                (len(channels_to_add) > 0 and added_count > 0) 
                or len(channels_to_add) == 0
            )
        ):
            return jsonify(
                success=True,
                confirmation_needed=False,
                add_names=add_names,
                remove_names=remove_names,
                total_count=get_subscriptions_count(user_id),
            )
        
        return error_return, 500
    
    except Exception as e:
        print(f"❌ update_subscriptions: update failed: {e}")
        return error_return, 500


@app.route('/google_login')
def google_login():
    """Automatically redirect to Google OAuth"""
    # Save target URL to return to after authorization
    next_url = request.args.get('next')
    if next_url:
        session['next_url'] = next_url

    return oauth.google.authorize_redirect(url_for('oauth2callback', _external=True))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return oauth.google.authorize_redirect(url_for('oauth2callback', _external=True), prompt='select_account')


@app.route('/oauth2callback')
def oauth2callback():
    """Get user info, check/create user, save subscriptions"""
    token = oauth.google.authorize_access_token()
    
    # Get user info from Google
    userinfo_url = 'https://www.googleapis.com/oauth2/v3/userinfo'
    response = requests.get(userinfo_url, params={'access_token': token['access_token']})
    user_info = response.json()
    google_id = user_info['sub']
    email = user_info['email']
    
    # Check if user exists / create user
    user_id = get_or_create_user(google_id, email)

    # Get list of subscriptions if there are none for this user
    if get_subscriptions_count(user_id) == 0:
        subscriptions = fetch_subscriptions(token['access_token'])
        result = save_subscriptions_bulk(user_id, subscriptions)
    
    # Set session, save token for later use and redirect to subscriptions
    session['user_id'] = user_id
    session['access_token'] = token['access_token']

    next_url = session.pop('next_url', None)
    return redirect(next_url or url_for('index'))


# Initialize database on startup
init_db()


if __name__ == "__main__":
    app.run(debug=True)