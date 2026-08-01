# YouTube Collections

# Video Demo: <URL HERE>

# Description

YouTube Collections is a Flask web application for organizing YouTube subscriptions into custom categories and browsing videos from those subscriptions through a filterable feed. This app's channel categories are similar to the setup of cable TV boxes, which organize TV channels into categories such as "Sports", "News", "Documentaries", etc.

The main reason for this project is that YouTube’s native applications do not provide this kind of user-defined category filtering for subscription feeds (whether created by the user or even by YouTube's own tags). Filtering is only possible on YouTube's "home" page, but that page includes recommended videos from outside the user's subscriptions, videos on the home page are not organized in any obvious way (such as by upload date), and the filters are YouTube's suggested tags, not categories explicitly defined by the user. YouTube's default subscription experience may work reasonably well for a small number of channels, but becomes difficult to manage once a user's subscriptions start spanning many unrelated interests such as programming, music, news, documentaries, travel, entertainment, etc.

This app gives control of the subscription-viewing experience back to the user by adding a personalized organizational layer on top of YouTube subscriptions. After signing in with a Google account and importing their current subscriptions, the user can group channels by custom user-defined categories and then browse videos that belong to any one category, as well as view other, uncategorized channels separately. The user can also simply view all videos from their subscriptions, just like YouTube's native subscriptions page, but with Shorts (short, vertical videos) mostly filtered out (a commonly desirable feature).

## What the project does

The main purpose of this project is to solve a specific usability problem: people often subscribe to many channels, but YouTube does not give them a simple way to group those channels into personal collections and then browse a category-specific feed.

The application is not just a thin wrapper around a public API — it does not simply fetch a page of videos directly from YouTube and show it. Instead, it stores channel and video data locally, checks whether any channels are yet to be refreshed at least once, fetches missing metadata such as durations, filters out unresolved entries and Shorts, returns feed results using a stable cursor, and decides whether older uploads must be fetched from one or more channels in order to properly fill future pages.

At a high level, the application combines several pieces of functionality into one workflow:
- Google OAuth login.
- Importing a user's YouTube subscriptions through the YouTube Data API.
- Fetching videos for a user's subscriptions through the YouTube Data API, as required for page serving.
- Fetching video metadata through the YouTube Data API, as required for page serving.
- Saving subscriptions, channels, categories, category assignments, and videos in SQLite.
- Displaying a merged subscriptions feed across many channels.
- Filtering that feed by custom user-defined categories.
- Filtering out YouTube Shorts for a more uniform viewing experience.
- Synchronizing the saved local subscription list with the user's current YouTube subscriptions.
- Refreshing and backfilling cached video uploads so the feed remains usable without needing to rebuild everything on every page load.

The app is doing significant coordination between database state, remote API data, refresh timing, and page-generation logic. This design is more complex than a standard Flask app with forms and tables, but that complexity is what makes the project useful.

The app is read-only with respect to YouTube itself. It does not subscribe, unsubscribe, or modify the user's YouTube account. Instead, it uses YouTube data as input and builds a better local browsing and organization experience on top of it.

## Main features

### Authentication

Users sign in through Google OAuth with read-only YouTube access. On successful login, the app reads the Google account identity, creates a local user record, and stores session information needed for future requests.

### Initial subscription import

When a user logs in for the first time, the app fetches the current list of YouTube subscriptions, as well as the most recent uploaded videos for each subscription, and stores everything locally. This allows the rest of the application to work from a local relational model instead of relying on repeated subscription API calls.

### Category management

Users can create, rename, and delete categories. Each subscribed channel can be assigned to one category or left uncategorized, which makes it possible to organize the user's YouTube account into personal topic-based collections such as "Science", “Travel”, “Fitness", etc.

### Filtered subscriptions feed

The main page template shows a combined feed of videos pulled from the user's subscribed channels. The feed can be viewed as:
- all subscribed channels,
- only channels assigned to one specific category,
- or only uncategorized channels.

This turns subscriptions into browseable collections rather than one large unstructured stream.

### Filtering out YouTube Shorts

The feed filters out YouTube Shorts in order to create a more uniform browsing experience. This was not just a presentation choice: it added complexity to the data pipeline because the uploads data fetched from YouTube can include Shorts, while duration data is not available from the uploads source alone.

To support this, the app stores uploaded videos first, fetches missing durations separately, and excludes videos whose duration falls below the configured threshold for normal videos. That means Shorts filtering is built into feed generation itself, not simply hidden in the front end.

### Load more pagination

The feed supports incremental loading through a cursor based on publication timestamp and video ID. This avoids expensive page rebuilding from scratch and gives the application a more predictable way to continue the merged feed.

### Refresh and backfill

The app caches video data in SQLite and fetches videos from channels selectively. If cached history is not deep enough to support the next page of the feed, the app can fetch older uploads from relevant channels and extend the local history only as far as needed.

### Subscription synchronization

The project includes update logic that compares the current YouTube subscription list with the saved local one. If the user has subscribed to new channels, those can be added locally. If the user has unsubscribed from channels, the app asks for confirmation before removing those channels and their related assignments from the local database.

## File structure

### Core Python files

#### `app.py`

This is the main Flask application. It defines the routes for the subscriptions feed, loading more results, refreshing subscriptions, the admin page, assigning channels, creating categories, deleting categories, renaming categories, updating subscriptions, logging in, logging out, and handling the OAuth callback.

It is responsible for coordinating the rest of the application: receiving requests, reading form and query parameters, calling database and API functions, managing session state, and rendering templates.

#### `database.py`

This file contains the SQLite data layer. It creates the database schema and implements most of the application's persistent logic.

Its responsibilities include:
- creating tables and indexes,
- saving subscriptions,
- saving and updating cached videos,
- managing categories,
- managing category assignments,
- detecting stale and never-refreshed channels,
- comparing remote and local subscription lists,
- and serving feed-related query results.

This file is especially important because the project depends heavily on local caching and relational queries rather than direct API-only rendering.

#### `youtube_api.py`

This file contains the integration with the YouTube Data API. It loads credentials, fetches subscriptions, fetches uploads from a channel's uploads playlist, fetches video metadata such as durations, and performs refresh operations for one or more channels.

It also contains some of the most important application logic, especially the code that builds the feed from cached data and decides when additional API requests are needed.

#### `helpers.py`

This file contains shared utility functions used across the project. These include date formatting, duration formatting, ISO datetime parsing, YouTube ISO 8601 duration parsing, string normalization for sorting, and sort-parameter parsing.

Keeping these functions separate makes the route and database code cleaner and easier to maintain.

### Templates

#### `templates/base.html`

Base template shared by the rest of the pages. It contains the common page structure and shared layout components, particularly the top navigation bar.

#### `templates/subscriptions.html`

Template for the main subscriptions feed. It renders the combined video list, feed filters, and controls related to loading and refreshing content.

#### `templates/admin.html`

Template for the admin and organization page. It renders the interface for managing categories, sorting channels, and assigning subscriptions to categories.

### Static CSS

#### `static/css/base.css`

Global styles shared across the application.

#### `static/css/subscriptions.css`

Page-specific styles for the main subscriptions feed.

#### `static/css/admin.css`

Page-specific styles for the admin interface.

### Static JavaScript

#### `static/js/auth_helpers.js`

Helpers related to authentication-driven front-end behavior.

#### `static/js/load_more.js`

Client-side logic for loading additional feed items without a full page refresh.

#### `static/js/refresh.js`

Client-side logic for triggering refresh actions.

#### `static/js/scroll_horizontal.js`

Handles horizontal scrolling behavior in the interface, particularly for elements in the top navigation bar.

#### `static/js/scroll_vertical.js`

Handles vertical scrolling behavior in the interface, particularly for hiding and showing the top navigation bar.

#### `static/js/admin_actions.js`

Shared helper logic for admin-page interactions.

#### `static/js/admin_assign.js`

Handles assigning channels to categories.

#### `static/js/admin_create.js`

Handles creating new categories.

#### `static/js/admin_delete.js`

Handles deleting categories.

#### `static/js/admin_rename.js`

Handles renaming categories.

#### `static/js/admin_sort.js`

Handles sorting behavior on the admin page.

#### `static/js/admin_update.js`

Handles updating state from the admin page, including subscription-management actions.

### Configuration and data files

#### `client_secret.json`

Stores the Google OAuth credentials and YouTube API key required by the application.

#### `youtube_collections.db`

SQLite database file created and used by the application.

## Database design

The project uses SQLite with a relational schema built around six main tables:
- `users`
- `channels`
- `subscriptions`
- `categories`
- `collections`
- `videos`

### `users`

Stores local application users mapped to Google accounts.

### `channels`

Stores channel-level information such as channel ID, name, refresh timestamps, saved pagination token, and whether historical backfill is complete.

### `subscriptions`

Stores which user is subscribed to which channel. This separates a user's relationship to a channel from the channel record itself, allowing for multiple users to be subscribed to the same channel.

### `categories`

Stores custom category names created by a user.

### `collections`

This is the junction table that links a user's subscribed channels to that user's categories. It is what makes the custom organization system possible.

### `videos`

Stores cached video metadata such as video ID, title, duration, publication timestamp, refresh timestamp, thumbnail URL, and channel association.

This schema was chosen to keep concerns separate:
- user identity is separate from subscriptions,
- subscriptions are separate from channels,
- categories are separate from subscriptions,
- and videos are cached independently from category assignment.

That separation makes it easier to update one part of the system without rebuilding everything else.

## How the feed works

The subscriptions feed is first built from local cached data rather than direct page-by-page rendering from YouTube.

When a user requests the feed, the application:
1. Determines which channels belong to the active filter.
2. Checks whether any of those channels have never been refreshed.
3. Performs an initial refresh for unrefreshed channels if necessary.
4. Reads candidate videos from the local database.
5. Detects whether any visible candidates are missing duration metadata.
6. Fetches and updates missing video metadata if necessary.
7. Excludes unresolved entries and YouTube Shorts from display.
8. Returns the next page of results using a cursor.
9. Checks whether additional historical uploads must be backfilled from some channels so pages can be served correctly.
10. Repeats steps 4 onward if not enough confirmed non-Shorts remain or if any videos were fetched in step 9.

Serving videos from the cached database and only fetching them as needed reduces dependence on repeated live API calls.

## YouTube API usage

The application relies on several different YouTube API calls, each with a different purpose.

### `subscriptions.list`

This call is used to import or synchronize the user's subscribed channels. It gives the list of subscriptions, including channel identity and subscription timestamps, but it does not provide a ready-to-use merged video feed.

### Channel uploads playlist requests

For each subscribed channel, the app fetches the channel's uploads playlist and reads recent uploaded videos from there. This is the source used to discover which videos exist for a channel, but those results can include Shorts and do not provide all of the metadata needed for final display.

### `videos.list`

After candidate videos are known, the app calls `videos.list` in batches based on the requirements of the current page rather than making a separate full metadata request per channel. This is where durations and other missing metadata are fetched. Metadata that has already been cached (like video titles and thumbnail URLs) is also updated.

That batching strategy was an important design choice. It reduces unnecessary requests, helps control quota use, and makes it possible to fetch metadata only for videos that are actually relevant to what the user is trying to load, shortening page load times.

## Design decisions and tradeoffs

### Managing YouTube API quota with incremental refresh

Probably the most important design tradeoff in this project was between completeness, loading speed and quota efficiency. A naive approach would be to refresh every subscribed channel in full whenever the user opens the feed, but that would generate a very large number of YouTube API requests and make the page extremely slow for users with many subscriptions.

Instead, the app loads from the local database first and only refreshes or backfills data when needed. Channels that have never been refreshed are initialized, stale channels can be refreshed on demand, and older uploads are fetched incrementally only when the cached history is not deep enough to support the next page of the merged feed.

If the user mostly browses and refreshes category pages rather than the full subscriptions page, the larger subscription list is effectively split into smaller units with more manageable API and loading costs.

This approach saves quota and makes the app much more usable, but the tradeoff is significantly more complex logic. The application has to track refresh timestamps, saved pagination tokens, backfill completion state, and cursor boundaries across many channels instead of simply showing whatever a single API call returns.

### Loading from database first instead of auto-refreshing

Another important tradeoff was deciding not to refresh subscriptions automatically every time the user opens the "All Subscriptions" page. Earlier in development, automatically refreshing that page could make it take over 12 minutes to load for a large subscription list.

The current design loads cached results from SQLite first and treats refresh as a separate explicit action. This makes the page much faster and avoids unnecessary API usage, but the tradeoff is that the first page may not always reflect the absolute newest uploads until the user refreshes relevant channels.

### Building a local category system

YouTube does not provide the exact personal grouping feature this project is built around, so categories are implemented locally. This gives the user flexible organization without depending on YouTube to support it.

The tradeoff is that these categories exist only within this application and are not reflected in the actual YouTube account.

### Confirming removals during subscription update

When synchronizing subscriptions, the app can ask for confirmation before removing channels that the user has unsubscribed from on YouTube. This makes the update safer because removing a channel locally can also remove its organization context from the app.

The tradeoff is an extra step in the update flow, but that step reduces accidental loss of local structure.

### Incremental historical backfill

The app does not try to fetch the full upload history of every subscribed channel during the first load. Instead, it fetches additional older uploads only when the cached data is not deep enough to support the next part of the feed.

This reduces unnecessary API usage and keeps the initial load more efficient. The tradeoff is that the feed-generation logic becomes more sophisticated because the app must reason about page boundaries and channel history depth.

## Limitations

There are also some limitations in the current design:
- The app depends on valid Google OAuth credentials (though this is arguably unavoidable) and a YouTube API key.
- The app is read-only with respect to YouTube and cannot change a user's subscriptions on YouTube itself.
- Feed completeness depends on what has already been cached and refreshed locally.
- Secrets are stored in a local JSON file for convenience, which is acceptable for a course project but not ideal for production.

## Running the project

1. Create and activate a Python virtual environment.
2. Install the required packages.
3. Add a valid `client_secret.json` file in the project root. It should contain your Google OAuth credentials, YouTube Data API key and Flask secret key. For example:
```json
{
  "web": {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "flask_secret_key": "YOUR_FLASK_SECRET_KEY",
    "youtube_api_key": "YOUR_YOUTUBE_API_KEY",
    "project_id": "YOUR_PROJECT_ID",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "redirect_uris": ["http://localhost:5000/oauth2callback"],
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```
4. Run `app.py`.
5. Open the app in a browser and sign in with Google.

## Conclusion

The main goal of YouTube Collections is to make subscriptions easier to manage by turning them into something the user can organize and browse intentionally. From a technical perspective, the project combines Flask, OAuth, the YouTube Data API, SQLite, client-side JavaScript, local caching, synchronization logic, and incremental feed generation into one application.

The result is a project that is both personally useful and technically more involved than a simple database app or a simple API viewer.
