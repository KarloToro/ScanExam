<script setup lang="ts">
const auth = useAuthStore()
const toast = useToast()

async function onLogout() {
  auth.logout()

  toast.add({
    title: 'Sesión cerrada',
    description: 'Has salido del panel docente.',
    color: 'neutral',
    icon: 'i-lucide-log-out'
  })

  await navigateTo('/login')
}
</script>

<template>
  <div>
    <UHeader>
      <template #left>
        <NuxtLink
          to="/"
          class="flex items-center gap-2 font-semibold text-highlighted"
        >
          <UIcon
            name="i-lucide-scan-line"
            class="size-5 text-primary"
          />
          <span>ScanExam</span>
        </NuxtLink>
      </template>

      <template #right>
        <div class="flex items-center gap-2">
          <span
            v-if="auth.user"
            class="hidden text-sm text-muted sm:inline"
          >
            {{ auth.user.username || auth.user.email }}
          </span>
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-log-out"
            aria-label="Cerrar sesión"
            @click="onLogout"
          >
            <span class="hidden sm:inline">Salir</span>
          </UButton>
          <UColorModeButton />
        </div>
      </template>
    </UHeader>

    <UMain>
      <slot />
    </UMain>

    <UFooter>
      <p class="text-sm text-muted">
        ScanExam — Panel docente · {{ new Date().getFullYear() }}
      </p>
    </UFooter>
  </div>
</template>
