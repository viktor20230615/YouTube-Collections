// Redirects to login page
async function redirectIfUnauthorized(response, { preserveNext = false } = {}) {
    if (response.status !== 401) {
        return false;
    }

    let loginUrl = '/google_login';

    try {
        const data = await response.json();
        if (data?.login_url) {
            loginUrl = data.login_url;
        }
    }
    catch (error) {
        console.warn('⚠️ Could not parse unauthorized response JSON:', error);
    }

    if (preserveNext) {
        const nextUrl = window.location.pathname + window.location.search;
        const separator = loginUrl.includes('?') ? '&' : '?';
        loginUrl = `${loginUrl}${separator}next=${encodeURIComponent(nextUrl)}`;
    }

    window.location.replace(loginUrl);
    return true;
}