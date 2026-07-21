import type { ExamAnswer, ExamStudent } from '~/utils/examCsv'
import {
  createAnswer,
  createStudent,
  isFilledAnswer,
  isFilledStudent,
  parseAnswersCsv,
  parseStudentsCsv,
  serializeAnswersCsv,
  serializeStudentsCsv,
  toCsvFile
} from '~/utils/examCsv'

export type ExamPackageUploadResult = {
  ok: boolean
  batch_id?: string
  message?: string
}

const IMAGE_EXTENSIONS = new Set([
  '.jpg',
  '.jpeg',
  '.png'
])

export function useExamPackageUpload() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()

  const images = shallowRef<File[]>([])
  const examName = shallowRef('')
  const students = ref<ExamStudent[]>([createStudent()])
  const answers = ref<ExamAnswer[]>([createAnswer({ question: '1' })])
  const isUploading = shallowRef(false)
  const error = shallowRef<string | null>(null)
  const result = shallowRef<ExamPackageUploadResult | null>(null)

  const filledStudents = computed(() => students.value.filter(isFilledStudent))
  const filledAnswers = computed(() => answers.value.filter(isFilledAnswer))
  const trimmedExamName = computed(() => examName.value.trim())

  const summary = computed(() => ({
    examName: trimmedExamName.value,
    imageCount: images.value.length,
    studentCount: filledStudents.value.length,
    answerCount: filledAnswers.value.length
  }))

  const canSubmit = computed(() =>
    trimmedExamName.value.length > 0
    && images.value.length > 0
    && filledStudents.value.length > 0
    && filledAnswers.value.length > 0
    && !isUploading.value
  )

  function markDirty() {
    error.value = null
    result.value = null
  }

  function setImages(next: File | File[] | null | undefined) {
    markDirty()

    const list = normalizeFileList(next)
    const invalid = list.find(file => !isImageFile(file))

    if (invalid) {
      images.value = []
      error.value = `"${invalid.name}" no es una imagen válida.`
      return
    }

    images.value = list
  }

  async function importStudentsCsv(next: File | File[] | null | undefined) {
    markDirty()

    const file = pickCsvFile(next, 'estudiantes')
    if (!file) {
      return
    }

    try {
      const text = await file.text()
      const parsed = parseStudentsCsv(text)

      if (!parsed.ok) {
        error.value = parsed.message
        return
      }

      students.value = parsed.data
    } catch {
      error.value = 'No se pudo leer el CSV de estudiantes.'
    }
  }

  async function importAnswersCsv(next: File | File[] | null | undefined) {
    markDirty()

    const file = pickCsvFile(next, 'respuestas')
    if (!file) {
      return
    }

    try {
      const text = await file.text()
      const parsed = parseAnswersCsv(text)

      if (!parsed.ok) {
        error.value = parsed.message
        return
      }

      answers.value = parsed.data
    } catch {
      error.value = 'No se pudo leer el CSV de respuestas.'
    }
  }

  function pickCsvFile(
    next: File | File[] | null | undefined,
    label: string
  ): File | null {
    const selected = Array.isArray(next) ? next[0] : next

    if (!selected) {
      return null
    }

    if (!isCsvFile(selected)) {
      error.value = `El archivo de ${label} debe ser un CSV.`
      return null
    }

    return selected
  }

  function clear() {
    images.value = []
    examName.value = ''
    students.value = [createStudent()]
    answers.value = [createAnswer({ question: '1' })]
    error.value = null
    result.value = null
  }

  function buildFormData(): FormData | null {
    if (
      !trimmedExamName.value
      || images.value.length === 0
      || filledStudents.value.length === 0
      || filledAnswers.value.length === 0
    ) {
      return null
    }

    const formData = new FormData()

    formData.append('name', trimmedExamName.value)

    for (const image of images.value) {
      formData.append('images', image)
    }

    formData.append(
      'students',
      toCsvFile(serializeStudentsCsv(filledStudents.value), 'estudiantes.csv')
    )
    formData.append(
      'answers',
      toCsvFile(serializeAnswersCsv(filledAnswers.value), 'respuestas.csv')
    )

    return formData
  }

  async function upload(): Promise<ExamPackageUploadResult | null> {
    if (!canSubmit.value || isUploading.value) {
      return null
    }

    auth.ensureValidSession()

    if (!auth.isAuthenticated || !auth.authorizationHeader) {
      error.value = 'Debes iniciar sesión para subir un examen.'
      await navigateTo('/login')
      return null
    }

    const endpoint = resolveExamUploadUrl(config.public.apiBaseUrl)

    if (!endpoint) {
      error.value = 'La URL de la API aún no está configurada (NUXT_PUBLIC_API_BASE_URL).'
      return null
    }

    const formData = buildFormData()

    if (!formData) {
      error.value = 'Completa el nombre de la prueba, las imágenes, al menos un estudiante y una respuesta.'
      return null
    }

    isUploading.value = true
    error.value = null
    result.value = null

    try {
      const response = await $fetch<ExamPackageUploadResult>(endpoint, {
        method: 'POST',
        body: formData,
        headers: {
          Authorization: auth.authorizationHeader
        }
      })

      if (!response?.ok) {
        if (import.meta.dev) {
          console.log(response)
        }
        error.value = 'No se pudo enviar el paquete. Inténtalo de nuevo.'
        return null
      }

      result.value = response
      return result.value
    } catch (err: unknown) {
      if (isUnauthorizedError(err)) {
        auth.logout()
        error.value = 'Tu sesión expiró. Inicia sesión de nuevo.'
        await navigateTo('/login')
        return null
      }

      error.value = getUploadErrorMessage(err)
      return null
    } finally {
      isUploading.value = false
    }
  }

  return {
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
    buildFormData,
    upload
  }
}

function normalizeFileList(next: File | File[] | null | undefined): File[] {
  if (!next) {
    return []
  }

  return Array.isArray(next) ? next : [next]
}

function isImageFile(file: File): boolean {
  return IMAGE_EXTENSIONS.has(getExtension(file.name))
}

function isCsvFile(file: File): boolean {
  if (getExtension(file.name) === '.csv') {
    return true
  }

  return file.type === 'text/csv' || file.type === 'application/csv'
}

function getExtension(filename: string): string {
  const index = filename.lastIndexOf('.')
  if (index === -1) {
    return ''
  }

  return filename.slice(index).toLowerCase()
}

function resolveExamUploadUrl(apiBaseUrl: unknown): string {
  const baseUrl = String(apiBaseUrl || '').replace(/\/$/, '')
  if (!baseUrl) {
    return ''
  }

  return `${baseUrl}/exams/upload`
}

function isUnauthorizedError(err: unknown): boolean {
  if (typeof err !== 'object' || err === null) {
    return false
  }

  if ('statusCode' in err && (err as { statusCode?: number }).statusCode === 401) {
    return true
  }

  return 'status' in err && (err as { status?: number }).status === 401
}

function getUploadErrorMessage(err: unknown): string {
  if (typeof err === 'object' && err !== null && 'data' in err) {
    const data = (err as {
      data?: ExamPackageUploadResult | { message?: string, statusMessage?: string } | string
    }).data

    if (typeof data === 'string' && data.trim()) {
      return data
    }

    if (typeof data === 'object' && data !== null) {
      if ('message' in data && typeof data.message === 'string' && data.message) {
        return data.message
      }
      if ('statusMessage' in data && typeof data.statusMessage === 'string' && data.statusMessage) {
        return data.statusMessage
      }
    }
  }

  if (err instanceof Error && err.message) {
    return err.message
  }

  return 'No se pudo enviar el paquete. Inténtalo de nuevo.'
}
