<script setup lang="ts">
const toast = useToast()
const {
  images,
  examName,
  students,
  answers,
  isUploading,
  error,
  result,
  summary,
  canSubmit,
  setImages,
  importStudentsCsv,
  importAnswersCsv,
  markDirty,
  clear,
  upload
} = useExamPackageUpload()

const imagesModel = computed({
  get: () => images.value,
  set: (value: File | File[] | null | undefined) => {
    setImages(value)
  }
})

async function onSubmit() {
  const uploaded = await upload()

  if (!uploaded) {
    return
  }

  toast.add({
    title: 'Paquete enviado',
    description: uploaded.batch_id
      ? `Lote ${uploaded.batch_id} enviado a revisión.`
      : 'La prueba se envió correctamente.',
    color: 'success',
    icon: 'i-lucide-circle-check'
  })
}
</script>

<template>
  <div class="space-y-8">
    <UFormField
      label="Nombre de la prueba"
      description="Identifica esta evaluación (por ejemplo: Parcial 1 — Matemáticas)."
      name="examName"
      required
    >
      <UInput
        v-model="examName"
        placeholder="Ej. Examen parcial de Física"
        size="lg"
        class="w-full"
        :disabled="isUploading"
        @update:model-value="markDirty"
      />
    </UFormField>

    <USeparator />

    <UFormField
      label="Imágenes de las fichas"
      description="Puedes seleccionar varias fotos o escaneos de las fichas de evaluación."
      name="images"
      required
    >
      <UFileUpload
        v-model="imagesModel"
        multiple
        accept=".jpg,.jpeg,.png,image/jpeg,image/png"
        label="Arrastra las imágenes aquí"
        description="JPG o PNG"
        icon="i-lucide-images"
        layout="list"
        class="w-full min-h-40"
        :disabled="isUploading"
        :ui="{
          base: 'min-h-40'
        }"
      />
    </UFormField>

    <USeparator />

    <UploadExamStudentsEditor
      v-model="students"
      :disabled="isUploading"
      @import-csv="importStudentsCsv"
      @change="markDirty"
    />

    <USeparator />

    <UploadExamAnswersEditor
      v-model="answers"
      :disabled="isUploading"
      @import-csv="importAnswersCsv"
      @change="markDirty"
    />

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      title="Error"
      :description="error"
      :ui="{
        description: 'whitespace-pre-line font-mono text-xs sm:text-sm'
      }"
    />

    <UAlert
      v-if="result"
      color="success"
      variant="subtle"
      icon="i-lucide-circle-check"
      title="Envío completado"
      description="El paquete se envió a la API correctamente."
    />

    <div class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default bg-elevated/50 px-4 py-3">
      <p class="text-sm text-muted">
        <span v-if="summary.examName">{{ summary.examName }} · </span>
        {{ summary.imageCount }} imagen(es)
        · {{ summary.studentCount }} estudiante(s)
        · {{ summary.answerCount }} respuesta(s)
      </p>

      <div class="flex items-center gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          :disabled="isUploading"
          @click="clear"
        >
          Limpiar
        </UButton>
        <UButton
          color="primary"
          icon="i-lucide-send"
          :loading="isUploading"
          :disabled="!canSubmit"
          @click="onSubmit"
        >
          Enviar a evaluación
        </UButton>
      </div>
    </div>
  </div>
</template>
