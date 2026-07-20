export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()
  auth.ensureValidSession()

  const isLoginRoute = to.path === '/login'

  if (isLoginRoute) {
    if (auth.isAuthenticated) {
      return navigateTo('/')
    }
    return
  }

  if (!auth.isAuthenticated) {
    return navigateTo({
      path: '/login',
      query: to.fullPath !== '/' ? { redirect: to.fullPath } : undefined
    })
  }
})
