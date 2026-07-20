<script setup lang="ts">
import type { ExamAnswer } from '~/utils/examCsv'
import { createAnswer } from '~/utils/examCsv'

const answers = defineModel<ExamAnswer[]>({ required: true })

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  importCsv: [file: File | File[] | null | undefined]
  change: []
}>()

const csvModel = shallowRef<File | null>(null)

const csvProxy = computed({
  get: () => csvModel.value,
  set: (value: File | File[] | null | undefined) => {
    const file = Array.isArray(value) ? value[0] ?? null : value ?? null
    csvModel.value = file
    emit('importCsv', value)
  }
})

function nextQuestionNumber(): string {
  const numbers = answers.value
    .map(answer => Number.parseInt(answer.question, 10))
    .filter(value => Number.isFinite(value))

  if (numbers.length === 0) {
    return String(answers.value.length + 1)
  }

  return String(Math.max(...numbers) + 1)
}

function addAnswer() {
  answers.value = [
    ...answers.value,
    createAnswer({ question: nextQuestionNumber() })
  ]
  emit('change')
}

function removeAnswer(id: string) {
  if (answers.value.length <= 1) {
    answers.value = [createAnswer({ question: '1' })]
  } else {
    answers.value = answers.value.filter(answer => answer.id !== id)
  }

  emit('change')
}

function onFieldChange() {
  emit('change')
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="font-medium text-highlighted">
          Clave de respuestas
        </p>
        <p class="text-sm text-muted">
          Escribe la clave y el puntaje de cada pregunta o importa un CSV (pregunta, clave, puntaje).
        </p>
      </div>

      <UFileUpload
        v-model="csvProxy"
        accept=".csv,text/csv,application/csv"
        label="Importar CSV"
        icon="i-lucide-file-spreadsheet"
        variant="button"
        size="sm"
        :disabled="props.disabled"
      />
    </div>

    <div class="space-y-3">
      <div
        v-for="answer in answers"
        :key="answer.id"
        class="grid gap-2 sm:grid-cols-[5.5rem_1fr_5.5rem_auto]"
      >
        <UInput
          v-model="answer.question"
          placeholder="Nº"
          :disabled="props.disabled"
          @update:model-value="onFieldChange"
        />
        <UInput
          v-model="answer.key"
          placeholder="Clave (A, B, C...)"
          :disabled="props.disabled"
          @update:model-value="onFieldChange"
        />
        <UInput
          v-model="answer.score"
          type="number"
          min="0"
          step="any"
          placeholder="Puntaje"
          :disabled="props.disabled"
          @update:model-value="onFieldChange"
        />
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-trash-2"
          aria-label="Eliminar respuesta"
          :disabled="props.disabled"
          @click="removeAnswer(answer.id)"
        />
      </div>
    </div>

    <UButton
      color="neutral"
      variant="soft"
      icon="i-lucide-plus"
      :disabled="props.disabled"
      @click="addAnswer"
    >
      Añadir pregunta
    </UButton>
  </div>
</template>
