<script setup lang="ts">
definePageMeta({
  layout: 'auth'
})

useSeoMeta({
  title: 'Iniciar sesión — ScanExam',
  description: 'Accede al panel docente de ScanExam.'
})

const auth = useAuthStore()
const route = useRoute()
const toast = useToast()

const login = ref('')
const password = ref('')
const showPassword = ref(false)

const canSubmit = computed(() =>
  login.value.trim().length > 0
  && password.value.length > 0
  && !auth.isLoading
)

async function onSubmit() {
  if (!canSubmit.value) {
    return
  }

  try {
    await auth.login(login.value, password.value)

    toast.add({
      title: 'Sesión iniciada',
      description: 'Bienvenido al panel docente.',
      color: 'success',
      icon: 'i-lucide-circle-check'
    })

    const redirect = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : '/'

    await navigateTo(redirect)
  } catch {
    // El mensaje queda en auth.error para mostrarlo en el formulario.
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-md space-y-8">
    <div class="space-y-3 text-center">
      <div class="mx-auto flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <UIcon
          name="i-lucide-scan-line"
          class="size-6"
        />
      </div>
      <h1 class="text-2xl font-semibold tracking-tight text-highlighted">
        Iniciar sesión
      </h1>
      <p class="text-muted text-pretty">
        Accede con tu usuario o correo para usar el panel docente.
      </p>
    </div>

    <UCard>
      <form
        class="space-y-5"
        @submit.prevent="onSubmit"
      >
        <UFormField
          label="Usuario o correo"
          name="login"
          required
        >
          <UInput
            v-model="login"
            type="text"
            autocomplete="username"
            placeholder="usuario o correo@institucion.com"
            size="lg"
            class="w-full"
            :disabled="auth.isLoading"
            icon="i-lucide-user"
          />
        </UFormField>

        <UFormField
          label="Contraseña"
          name="password"
          required
        >
          <UInput
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="Tu contraseña"
            size="lg"
            class="w-full"
            :disabled="auth.isLoading"
            icon="i-lucide-lock"
            :ui="{ trailing: 'pe-1' }"
          >
            <template #trailing>
              <UButton
                :icon="showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
                color="neutral"
                variant="ghost"
                size="sm"
                type="button"
                :aria-label="showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'"
                :disabled="auth.isLoading"
                @click="showPassword = !showPassword"
              />
            </template>
          </UInput>
        </UFormField>

        <UAlert
          v-if="auth.error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          title="No se pudo iniciar sesión"
          :description="auth.error"
        />

        <UButton
          type="submit"
          size="lg"
          block
          :loading="auth.isLoading"
          :disabled="!canSubmit"
          icon="i-lucide-log-in"
        >
          Entrar
        </UButton>
      </form>
    </UCard>
  </div>
</template>
