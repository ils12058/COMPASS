// Local synthetic preview for a native browser that cannot intercept requests.
// All API paths terminate here; no request can reach a real COMPASS API.
import http from 'node:http';
import { appointment, service, user } from './ui-hierarchy-fixtures.mjs';
const empty = { items: [], page: 1, page_size: 20, has_next: false };
const student = { ...user('STUDENT'), capabilities: ['appointments.view_self', 'appointments.manage_self', 'services.catalog.view'] };
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:3112');
  if (url.pathname.startsWith('/api/')) {
    let status = 200;
    let body;
    if (req.method !== 'GET') { status = 500; body = { error: { code: 'synthetic_preview', message: 'Preview only' } }; }
    else if (url.pathname === '/api/v1/auth/session') body = { user: student, session: { id: 'synthetic-preview', expires_at: '2099-01-01T00:00:00Z', is_current: true } };
    else if (url.pathname === '/api/v1/me/profile') body = { full_name: 'Example Student', photo: null };
    else if (url.pathname === '/api/v1/platform/status') body = { status: 'operational', message: null, starts_at: null, ends_at: null };
    else if (url.pathname === '/api/v1/notifications/unread-count') body = { unread_count: 0 };
    else if (url.pathname === '/api/v1/notifications/push/config') body = { enabled: false, vapid_public_key: null };
    else if (url.pathname === '/api/v1/appointments/booking/services') body = { ...empty, items: [service] };
    else if (url.pathname === '/api/v1/appointments/booking/counselors') body = { items: [{ ...appointment.provider, is_default: true, profile_photo_url: null, profile_photo_updated_at: null }, { id: 'synthetic-other', display_name: 'Alexandra Gabriella Delos Santos Villanueva', is_default: false, profile_photo_url: null, profile_photo_updated_at: null }] };
    else if (url.pathname === '/api/v1/appointments/booking/slots') body = { timezone: 'Asia/Manila', duration_minutes: 60, items: [2,3,4,5].map(hour => ({ starts_at: `${url.searchParams.get('date')}T0${hour}:00:00Z`, ends_at: `${url.searchParams.get('date')}T0${hour+1}:00:00Z` })) };
    else if (['/api/v1/notifications', '/api/v1/privacy/my-notices'].includes(url.pathname)) body = empty;
    else { status = 404; body = { error: { code: 'synthetic_unavailable' } }; }
    res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(body));
    return;
  }
  const proxy = http.request({ hostname: '127.0.0.1', port: 3107, path: req.url, method: req.method, headers: { ...req.headers, host: '127.0.0.1:3107' } }, upstream => {
    res.writeHead(upstream.statusCode, upstream.headers);
    upstream.pipe(res);
  });
  proxy.on('error', () => { res.writeHead(502); res.end('Start the local frontend on port 3107.'); });
  req.pipe(proxy);
});
server.listen(3112, '127.0.0.1', () => console.log('Synthetic appointment preview: http://127.0.0.1:3112/portal/appointments/book'));
