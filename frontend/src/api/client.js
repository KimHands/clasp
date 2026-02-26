const BASE_URL = 'http://localhost:8000'

async function request(method, path, body = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) {
    options.body = JSON.stringify(body)
  }

  const res = await fetch(`${BASE_URL}${path}`, options)
  const json = await res.json()

  if (!json.success) {
    const err = new Error(json.error?.message || '요청 실패')
    err.code = json.error?.code
    throw err
  }

  return json.data
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  patch: (path, body) => request('PATCH', path, body),
  delete: (path) => request('DELETE', path),
}

export { BASE_URL }
