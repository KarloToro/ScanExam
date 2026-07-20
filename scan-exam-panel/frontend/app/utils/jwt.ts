export type JwtPayload = {
  sub?: string
  username?: string
  email?: string
  exp?: number
  iat?: number
}

export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split('.')
    const payload = parts[1]

    if (!payload) {
      return null
    }

    const json = base64UrlDecode(payload)
    return JSON.parse(json) as JwtPayload
  } catch {
    return null
  }
}

export function isJwtExpired(token: string, skewSeconds = 30): boolean {
  const payload = decodeJwtPayload(token)

  if (!payload?.exp) {
    return true
  }

  return payload.exp * 1000 <= Date.now() + skewSeconds * 1000
}

function base64UrlDecode(input: string): string {
  const normalized = input.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(
    normalized.length + ((4 - (normalized.length % 4)) % 4),
    '='
  )

  const binary = atob(padded)
  const bytes = Uint8Array.from(binary, char => char.charCodeAt(0))
  return new TextDecoder().decode(bytes)
}
