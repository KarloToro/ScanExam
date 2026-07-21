<script setup lang="ts">
import type { ExamStudent } from '~/utils/examCsv'
import { createStudent } from '~/utils/examCsv'

const students = defineModel<ExamStudent[]>({ required: true })

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

function addStudent() {
  students.value = [...students.value, createStudent()]
  emit('change')
}

function removeStudent(id: string) {
  if (students.value.length <= 1) {
    students.value = [createStudent()]
  } else {
    students.value = students.value.filter(student => student.id !== id)
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
          Estudiantes
        </p>
        <p class="text-sm text-muted">
          Añádelos a mano o importa un CSV (codigo, nombre, correo).
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
        v-for="student in students"
        :key="student.id"
        class="grid gap-2 sm:grid-cols-[8rem_1fr_1.2fr_auto]"
      >
        <UInput
          v-model="student.code"
          placeholder="Código"
          :disabled="props.disabled"
          @update:model-value="onFieldChange"
        />
        <UInput
          v-model="student.name"
          placeholder="Nombre completo"
          :disabled="props.disabled"
          @update:model-value="onFieldChange"
        />
        <UInput
          v-model="student.email"
          type="email"
          placeholder="Correo"
          :disabled="props.disabled"
          @update:model-value="onFieldChange"
        />
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-trash-2"
          aria-label="Eliminar estudiante"
          :disabled="props.disabled"
          @click="removeStudent(student.id)"
        />
      </div>
    </div>

    <UButton
      color="neutral"
      variant="soft"
      icon="i-lucide-plus"
      :disabled="props.disabled"
      @click="addStudent"
    >
      Añadir estudiante
    </UButton>
  </div>
</template>
