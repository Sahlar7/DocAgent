console.log('DocAgent background script loaded');

let cachedToken = null;
let tokenExpiryTime = null;

chrome.runtime.onInstalled.addListener(() => {
    console.log('DocAgent Extension installed');
});

chrome.runtime.onStartup.addListener(() => {
    console.log('DocAgent Extension started');
});

/**
 * Get a valid OAuth token for Google Docs API
 */
async function getAuthToken(interactive = false) {
    return new Promise((resolve, reject) => {
        if (cachedToken && tokenExpiryTime && Date.now() < tokenExpiryTime) {
            console.log('Using cached OAuth token');
            resolve(cachedToken);
            return;
        }

        console.log('Requesting new OAuth token...');
        chrome.identity.getAuthToken({ interactive }, (token) => {
            if (chrome.runtime.lastError) {
                console.error('OAuth error:', chrome.runtime.lastError);
                reject(chrome.runtime.lastError);
            } else if (token) {
                console.log('OAuth token obtained');
                cachedToken = token;
                // Tokens typically expire in 1 hour, cache for 50 minutes
                tokenExpiryTime = Date.now() + (50 * 60 * 1000);
                resolve(token);
            } else {
                reject(new Error('No token returned'));
            }
        });
    });
}

/**
 * Clear cached token and get a fresh one
 */
async function refreshAuthToken() {
    return new Promise((resolve, reject) => {
        if (cachedToken) {
            chrome.identity.removeCachedAuthToken({ token: cachedToken }, () => {
                cachedToken = null;
                tokenExpiryTime = null;
                
                // Get a new token
                getAuthToken(true)
                    .then(resolve)
                    .catch(reject);
            });
        } else {
            getAuthToken(true)
                .then(resolve)
                .catch(reject);
        }
    });
}

/**
 * Handle messages from content script
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('Message received in background:', request.type);

    switch (request.type) {
        case 'GET_AUTH_TOKEN':
            // Get OAuth token for API calls
            getAuthToken(request.interactive || false)
                .then(token => {
                    sendResponse({ success: true, token });
                })
                .catch(error => {
                    console.error('Failed to get auth token:', error);
                    sendResponse({ success: false, error: error.message });
                });
            return true; // Will respond asynchronously

        case 'REFRESH_AUTH_TOKEN':
            // Force refresh the token
            refreshAuthToken()
                .then(token => {
                    sendResponse({ success: true, token });
                })
                .catch(error => {
                    console.error('Failed to refresh auth token:', error);
                    sendResponse({ success: false, error: error.message });
                });
            return true; // Will respond asynchronously

        case 'REVOKE_AUTH_TOKEN':
            // Revoke the current token
            if (cachedToken) {
                chrome.identity.removeCachedAuthToken({ token: cachedToken }, () => {
                    cachedToken = null;
                    tokenExpiryTime = null;
                    sendResponse({ success: true });
                });
            } else {
                sendResponse({ success: true });
            }
            return true; // Will respond asynchronously

        case 'TOGGLE_SIDEBAR':
            // Simple toggle functionality
            sendResponse({ success: true });
            break;

        case 'CHECK_AUTH_STATUS':
            // Check if we have a valid token
            sendResponse({
                success: true,
                hasToken: cachedToken !== null,
                tokenValid: cachedToken && tokenExpiryTime && Date.now() < tokenExpiryTime
            });
            break;

        default:
            console.log('Unknown message type:', request.type);
            sendResponse({ success: false, error: 'Unknown message type' });
    }

    return false; // Synchronous response
});

/**
 * Handle OAuth redirect flow (if using redirect-based OAuth)
 */
chrome.identity.onSignInChanged.addListener((account, signedIn) => {
    console.log('Sign-in status changed:', signedIn ? 'signed in' : 'signed out');
    if (!signedIn) {
        cachedToken = null;
        tokenExpiryTime = null;
    }
});

console.log('DocAgent background script ready with OAuth support');