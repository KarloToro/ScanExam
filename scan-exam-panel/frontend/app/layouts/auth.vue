<template>
  <div class="min-h-screen">
    <UHeader>
      <template #left>
        <div class="flex items-center gap-2 font-semibold text-highlighted">
          <UIcon
            name="i-lucide-scan-line"
            class="size-5 text-primary"
          />
          <span>ScanExam</span>
        </div>
      </template>

      <template #right>
        <UColorModeButton />
      </template>
    </UHeader>

    <UMain>
      <UContainer class="flex min-h-[calc(100vh-8rem)] items-center py-10">
        <slot />
      </UContainer>
    </UMain>
  </div>
</template>
