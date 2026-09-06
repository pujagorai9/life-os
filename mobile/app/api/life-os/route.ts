const DEFAULT_API_URL = 'http://127.0.0.1:8000';

async function proxy(request: Request) {
  const requestUrl = new URL(request.url);
  const path = requestUrl.searchParams.get('path');
  if (!path || (!path.startsWith('/v1/') && path !== '/health')) {
    return Response.json(
      { detail: 'A valid Life OS API path is required.' },
      { status: 400 },
    );
  }

  const apiRoot = (process.env.LIFE_OS_API_URL || DEFAULT_API_URL).replace(
    /\/$/,
    '',
  );
  const headers = new Headers();
  const contentType = request.headers.get('content-type');
  if (contentType) headers.set('content-type', contentType);
  const apiToken = process.env.LIFE_OS_API_TOKEN?.trim();
  const authorization = request.headers.get('authorization');
  if (apiToken) {
    headers.set('authorization', `Bearer ${apiToken}`);
  } else if (authorization) {
    headers.set('authorization', authorization);
  }
  const upstreamUrl = new URL(`${apiRoot}${path}`);
  requestUrl.searchParams.forEach((value, key) => {
    if (key !== 'path') upstreamUrl.searchParams.append(key, value);
  });

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body:
        request.method === 'GET' || request.method === 'HEAD'
          ? undefined
          : await request.arrayBuffer(),
      cache: 'no-store',
    });
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        'content-type':
          upstream.headers.get('content-type') || 'application/json',
      },
    });
  } catch {
    return Response.json(
      { detail: 'The private Life OS service is unavailable.' },
      { status: 503 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
