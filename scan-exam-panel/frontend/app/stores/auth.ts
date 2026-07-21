import { acceptHMRUpdate, defineStore } from 'pinia'
import { decodeJwtPayload, isJwtExpired } from '~/utils/jwt'

export type AuthUser = {
  id: string
  username: string
  email: string
}

export type LoginResponse = {
  token: string
  token_type: string
  expires_in: number
}

const TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24

export const useAuthStore = defineStore('auth', () => {
  const config = useRuntimeConfig()
  const requestURL = useRequestURL()
  const tokenCookie = useCookie<string | null>('auth_token', {
    maxAge: TOKEN_COOKIE_MAX_AGE,
    sameSite: 'lax',
    secure: requestURL.protocol === 'https:',
    watch: true
  })

  const token = computed({
    get: () => tokenCookie.value,
    set: (value) => {
      tokenCookie.value = value
    }
  })
  const user = ref<AuthUser | null>(userFromToken(token.value))
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => {
    if (!token.value) {
      return false
    }

    return !isJwtExpired(token.value)
  })

  const authorizationHeader = computed(() => {
    if (!isAuthenticated.value || !token.value) {
      return null
    }

    return `Bearer ${token.value}`
  })

  watch(token, (value) => {
    user.value = userFromToken(value)
  })

  async function login(loginValue: string, password: string) {
    const baseUrl = String(config.public.apiBaseUrl || '').replace(/\/$/, '')

    if (!baseUrl) {
      if (import.meta.dev) {
        console.error('La URL de la API no está configurada (NUXT_PUBLIC_API_BASE_URL).')
      }

      error.value = 'No se pudo iniciar sesión. Inténtalo de nuevo.'
      throw new Error(error.value)
    }

    isLoading.value = true
    error.value = null

    try {
      const response = await $fetch<LoginResponse>(`${baseUrl}/auth/login`, {
        method: 'POST',
        body: {
          login: loginValue.trim(),
          password
        }
      })

      setSession(response.token)
      return response
    } catch (err: unknown) {
      clearSession()
      error.value = getLoginErrorMessage(err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    clearSession()
    error.value = null
  }

  function setSession(nextToken: string) {
    if (isJwtExpired(nextToken)) {
      clearSession()
      error.value = 'La sesión ha expirado. Inicia sesión de nuevo.'
      return
    }

    token.value = nextToken
    user.value = userFromToken(nextToken)
    error.value = null
  }

  function clearSession() {
    token.value = null
    user.value = null
  }

  function ensureValidSession() {
    if (token.value && isJwtExpired(token.value)) {
      clearSession()
    }
  }

  return {
    token,
    user,
    isLoading,
    error,
    isAuthenticated,
    authorizationHeader,
    login,
    logout,
    setSession,
    clearSession,
    ensureValidSession
  }
})

function userFromToken(token: string | null): AuthUser | null {
  if (!token || isJwtExpired(token)) {
    return null
  }

  const payload = decodeJwtPayload(token)

  if (!payload?.sub) {
    return null
  }

  return {
    id: payload.sub,
    username: payload.username ?? '',
    email: payload.email ?? ''
  }
}

function getLoginErrorMessage(err: unknown): string {
  const status = getErrorStatus(err)

  if (status === 401) {
    return 'Usuario o contraseña incorrectos.'
  }
  if (status === 400) {
    return 'Revisa el usuario y la contraseña.'
  }

  return 'No se pudo iniciar sesión. Inténtalo de nuevo.'
}

function getErrorStatus(err: unknown): number | undefined {
  if (typeof err !== 'object' || err === null) {
    return undefined
  }

  if ('statusCode' in err && typeof (err as { statusCode?: unknown }).statusCode === 'number') {
    return (err as { statusCode: number }).statusCode
  }

  if ('status' in err && typeof (err as { status?: unknown }).status === 'number') {
    return (err as { status: number }).status
  }

  return undefined
}

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useAuthStore, import.meta.hot))
}
