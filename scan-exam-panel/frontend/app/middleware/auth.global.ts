export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()
  auth.ensureValidSession()

  const isPublicRoute = to.path === '/login' || to.path === '/consulta' || to.path.startsWith('/consulta/')

  if (isPublicRoute) {
    if (to.path === '/login' && auth.isAuthenticated) {
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
