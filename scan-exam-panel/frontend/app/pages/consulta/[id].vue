<script setup lang="ts">
import type { StudentResult } from '~/utils/studentResult'
import { formatDetectedAnswer } from '~/utils/studentResult'

definePageMeta({
  layout: 'auth'
})

useSeoMeta({
  title: 'Consultar resultado — ScanExam',
  description: 'Consulta tu nota y las respuestas detectadas con tu clave de acceso.'
})

const route = useRoute()
const config = useRuntimeConfig()
const toast = useToast()

const resultId = computed(() => String(route.params.id || '').trim())

const accessKey = ref('')
const isLoading = ref(false)
const error = ref('')
const result = ref<StudentResult | null>(null)

const canSubmit = computed(() =>
  resultId.value.length > 0
  && accessKey.value.trim().length > 0
  && !isLoading.value
)

const answerColumns = [
  { accessorKey: 'question_id', header: 'Pregunta' },
  { accessorKey: 'detected', header: 'Tu respuesta' },
  { accessorKey: 'correct_answer', header: 'Correcta' },
  { accessorKey: 'status', header: 'Estado' },
  { accessorKey: 'points', header: 'Puntos' }
]

const answerRows = computed(() => {
  if (!result.value) {
    return []
  }
  return result.value.answers.map(answer => ({
    question_id: answer.question_id,
    detected: formatDetectedAnswer(answer.detected_answer),
    correct_answer: answer.correct_answer || '—',
    status: formatQuestionStatus(answer.question_status),
    points: `${formatNumber(answer.earned_points)} / ${formatNumber(answer.points)}`
  }))
})

function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return '—'
  }
  return value.toFixed(2)
}

function formatQuestionStatus(status: string): string {
  switch (status) {
    case 'CORRECT':
      return 'Correcta'
    case 'INCORRECT':
      return 'Incorrecta'
    case 'BLANK':
      return 'En blanco'
    case 'MULTIPLE':
      return 'Múltiple'
    default:
      return status || '—'
  }
}

async function onSubmit() {
  if (!canSubmit.value) {
    return
  }

  error.value = ''
  result.value = null
  isLoading.value = true

  try {
    const baseUrl = String(config.public.apiBaseUrl || '').replace(/\/$/, '')
    if (!baseUrl) {
      error.value = 'La URL de la API no está configurada.'
      return
    }

    result.value = await $fetch<StudentResult>(`${baseUrl}/results/lookup`, {
      method: 'POST',
      body: {
        id: resultId.value,
        access_key: accessKey.value.trim()
      }
    })
  } catch (err: unknown) {
    result.value = null
    const status = typeof err === 'object' && err !== null && 'statusCode' in err
      ? Number((err as { statusCode?: number }).statusCode)
      : undefined
    const message = typeof err === 'object' && err !== null && 'data' in err
      ? (err as { data?: { message?: string } }).data?.message
      : undefined

    if (status === 404) {
      error.value = message || 'Clave inválida o resultado no disponible.'
    } else {
      error.value = message || 'No se pudo consultar el resultado. Intenta de nuevo.'
    }

    toast.add({
      title: 'Consulta fallida',
      description: error.value,
      color: 'error',
      icon: 'i-lucide-circle-alert'
    })
  } finally {
    isLoading.value = false
  }
}

function escapeCsv(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replaceAll('"', '""')}"`
  }
  return value
}

function onDownload() {
  if (!result.value) {
    return
  }

  const data = result.value
  const lines = [
    ['evaluacion', 'estudiante', 'nota', 'nota_maxima', 'porcentaje'].map(escapeCsv).join(','),
    [
      data.exam_name,
      data.student_name || '',
      formatNumber(data.score),
      formatNumber(data.max_score),
      formatNumber(data.percentage)
    ].map(escapeCsv).join(','),
    '',
    ['pregunta', 'tu_respuesta', 'respuesta_correcta', 'estado', 'puntos_obtenidos', 'puntos'].map(escapeCsv).join(',')
  ]

  for (const answer of data.answers) {
    lines.push([
      String(answer.question_id),
      formatDetectedAnswer(answer.detected_answer),
      answer.correct_answer || '',
      formatQuestionStatus(answer.question_status),
      formatNumber(answer.earned_points),
      formatNumber(answer.points)
    ].map(escapeCsv).join(','))
  }

  const blob = new Blob([`${lines.join('\n')}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const slug = data.exam_name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'resultado'

  link.href = url
  link.download = `resultado-${slug}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="mx-auto w-full max-w-3xl space-y-8">
    <div class="space-y-3 text-center">
      <div class="mx-auto flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <UIcon
          name="i-lucide-clipboard-check"
          class="size-6"
        />
      </div>
      <h1 class="text-2xl font-semibold tracking-tight text-highlighted">
        Consultar resultado
      </h1>
      <p class="text-muted text-pretty">
        Ingresa la clave que recibiste por correo para ver tu nota y las respuestas detectadas.
      </p>
    </div>

    <UAlert
      v-if="!resultId"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      title="Enlace incompleto"
      description="Falta el identificador del resultado. Usa el enlace que recibiste por correo."
    />

    <UCard v-else-if="!result">
      <form
        class="space-y-5"
        @submit.prevent="onSubmit"
      >
        <UFormField
          label="Clave de acceso"
          name="access_key"
          required
        >
          <UInput
            v-model="accessKey"
            type="text"
            autocomplete="off"
            placeholder="Pega aquí tu clave"
            size="lg"
            class="w-full font-mono"
            :disabled="isLoading"
            icon="i-lucide-key-round"
          />
        </UFormField>

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          title="No se pudo consultar"
          :description="error"
        />

        <UButton
          type="submit"
          size="lg"
          block
          :loading="isLoading"
          :disabled="!canSubmit"
          icon="i-lucide-search"
        >
          Consultar
        </UButton>
      </form>
    </UCard>

    <div
      v-else
      class="space-y-6"
    >
      <UCard>
        <div class="space-y-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="space-y-1">
              <p class="text-sm text-muted">
                Evaluación
              </p>
              <h2 class="text-xl font-semibold text-highlighted">
                {{ result.exam_name }}
              </h2>
              <p
                v-if="result.student_name"
                class="text-muted"
              >
                {{ result.student_name }}
              </p>
            </div>
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-download"
              @click="onDownload"
            >
              Descargar resultados
            </UButton>
          </div>

          <div class="grid gap-4 sm:grid-cols-3">
            <div class="rounded-lg bg-elevated p-4">
              <p class="text-sm text-muted">
                Nota
              </p>
              <p class="mt-1 text-2xl font-semibold text-highlighted">
                {{ formatNumber(result.score) }}
                <span class="text-base font-normal text-muted">
                  / {{ formatNumber(result.max_score) }}
                </span>
              </p>
            </div>
            <div class="rounded-lg bg-elevated p-4 sm:col-span-2">
              <p class="text-sm text-muted">
                Porcentaje
              </p>
              <p class="mt-1 text-2xl font-semibold text-highlighted">
                {{ formatNumber(result.percentage) }}%
              </p>
            </div>
          </div>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h3 class="font-semibold text-highlighted">
            Detalle por pregunta
          </h3>
        </template>

        <UTable
          v-if="answerRows.length > 0"
          :data="answerRows"
          :columns="answerColumns"
          class="w-full"
        />
        <p
          v-else
          class="text-muted"
        >
          No hay detalle de respuestas para este resultado.
        </p>
      </UCard>
    </div>
  </div>
</template>
