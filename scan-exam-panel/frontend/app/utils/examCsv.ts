export type ExamStudent = {
  id: string
  code: string
  name: string
  email: string
}

export type ExamAnswer = {
  id: string
  question: string
  key: string
  score: string
}

export type CsvParseResult<T>
  = | { ok: true, data: T[] }
    | { ok: false, message: string }

export const STUDENTS_CSV_EXAMPLE = [
  'codigo,nombre,correo',
  '20240001,Pedro Sota,pedro.sota@example.com',
  '20240002,Ana Rojas,ana.rojas@example.com',
  '20240003,Luis Vega,luis.vega@example.com'
].join('\n')

export const ANSWERS_CSV_EXAMPLE = [
  'pregunta,clave,puntaje',
  '1,A,2',
  '2,B,2',
  '3,C,2',
  '4,D,2',
  '5,E,2'
].join('\n')

export function createStudent(partial?: Partial<Omit<ExamStudent, 'id'>>): ExamStudent {
  return {
    id: crypto.randomUUID(),
    code: partial?.code ?? '',
    name: partial?.name ?? '',
    email: partial?.email ?? ''
  }
}

export function createAnswer(partial?: Partial<Omit<ExamAnswer, 'id'>>): ExamAnswer {
  return {
    id: crypto.randomUUID(),
    question: partial?.question ?? '',
    key: partial?.key ?? '',
    score: partial?.score ?? '2'
  }
}

export function parseStudentsCsv(text: string): CsvParseResult<ExamStudent> {
  const rows = parseCsv(text)

  if (rows.length === 0) {
    return failStudents('El archivo está vacío.')
  }

  const rawHeader = rows[0]!
  const header = rawHeader.map(normalizeHeader)
  const mapping = resolveColumnMapping(header, STUDENT_COLUMNS)

  if (!mapping.ok) {
    return failStudents(mapping.message)
  }

  const dataRows = rows.slice(1)
  const codeIndex = mapping.indexes.code as number
  const nameIndex = mapping.indexes.name as number
  const emailIndex = mapping.indexes.email as number
  const students = dataRows
    .map((row) => {
      const code = (row[codeIndex] ?? '').trim()
      const name = (row[nameIndex] ?? '').trim()
      const email = (row[emailIndex] ?? '').trim()

      if (!code && !name && !email) {
        return null
      }

      return createStudent({ code, name, email })
    })
    .filter((row): row is ExamStudent => row !== null)

  if (students.length === 0) {
    return failStudents('No se encontraron filas de estudiantes.')
  }

  const incomplete = students.find(student => !isFilledStudent(student))
  if (incomplete) {
    return failStudents(
      'Hay filas incompletas: cada estudiante debe tener codigo, nombre y correo.'
    )
  }

  return { ok: true, data: students }
}

export function parseAnswersCsv(text: string): CsvParseResult<ExamAnswer> {
  const rows = parseCsv(text)

  if (rows.length === 0) {
    return failAnswers('El archivo está vacío.')
  }

  const header = rows[0]!.map(normalizeHeader)
  const mapping = resolveColumnMapping(header, ANSWER_COLUMNS)

  if (!mapping.ok) {
    return failAnswers(mapping.message)
  }

  const dataRows = rows.slice(1)
  const questionIndex = mapping.indexes.question as number
  const keyIndex = mapping.indexes.key as number
  const scoreIndex = mapping.indexes.score as number
  const answers = dataRows
    .map((row) => {
      const question = (row[questionIndex] ?? '').trim()
      const key = (row[keyIndex] ?? '').trim()
      const score = (row[scoreIndex] ?? '').trim()

      if (!question && !key && !score) {
        return null
      }

      return createAnswer({ question, key, score })
    })
    .filter((row): row is ExamAnswer => row !== null)

  if (answers.length === 0) {
    return failAnswers('No se encontraron filas de respuestas.')
  }

  const incomplete = answers.find(answer => !isFilledAnswer(answer))
  if (incomplete) {
    return failAnswers(
      'Hay filas incompletas: cada fila debe tener pregunta, clave y un puntaje mayor que 0.'
    )
  }

  return { ok: true, data: answers }
}

export function serializeStudentsCsv(students: ExamStudent[]): string {
  const lines = [
    ['codigo', 'nombre', 'correo'],
    ...students.map(student => [
      student.code.trim(),
      student.name.trim(),
      student.email.trim()
    ])
  ]

  return serializeCsv(lines)
}

export function serializeAnswersCsv(answers: ExamAnswer[]): string {
  const lines = [
    ['pregunta', 'clave', 'puntaje'],
    ...answers.map(answer => [
      answer.question.trim(),
      answer.key.trim(),
      answer.score.trim()
    ])
  ]

  return serializeCsv(lines)
}

export function toCsvFile(content: string, filename: string): File {
  return new File([content], filename, { type: 'text/csv' })
}

export function isFilledStudent(student: ExamStudent): boolean {
  return Boolean(
    student.code.trim()
    && student.name.trim()
    && student.email.trim()
  )
}

export function isFilledAnswer(answer: ExamAnswer): boolean {
  const score = Number(answer.score.trim().replace(',', '.'))

  return Boolean(
    answer.question.trim()
    && answer.key.trim()
    && Number.isFinite(score)
    && score > 0
  )
}

type ColumnDef = {
  key: string
  label: string
  aliases: Set<string>
}

const STUDENT_COLUMNS: ColumnDef[] = [
  {
    key: 'code',
    label: 'codigo',
    aliases: new Set(['codigo', 'code', 'student_code', 'codigo_estudiante'])
  },
  {
    key: 'name',
    label: 'nombre',
    aliases: new Set(['nombre', 'name', 'student_name', 'nombre_completo'])
  },
  {
    key: 'email',
    label: 'correo',
    aliases: new Set(['correo', 'email', 'mail', 'correo_electronico'])
  }
]

const ANSWER_COLUMNS: ColumnDef[] = [
  {
    key: 'question',
    label: 'pregunta',
    aliases: new Set(['pregunta', 'numero', 'nro', 'question', 'question_id'])
  },
  {
    key: 'key',
    label: 'clave',
    aliases: new Set(['clave', 'respuesta', 'correcta', 'correct_answer', 'answer'])
  },
  {
    key: 'score',
    label: 'puntaje',
    aliases: new Set(['puntaje', 'puntos', 'points', 'score', 'valor', 'peso'])
  }
]

type ColumnMappingSuccess = {
  ok: true
  indexes: Record<string, number>
}

type ColumnMappingFailure = {
  ok: false
  message: string
}

function resolveColumnMapping(
  header: string[],
  columns: ColumnDef[]
): ColumnMappingSuccess | ColumnMappingFailure {
  if (header.length === 0 || header.every(cell => cell === '')) {
    return { ok: false, message: 'Falta la fila de cabeceras.' }
  }

  const allowed = new Set(columns.flatMap(column => [...column.aliases]))
  const unknown = header.filter(cell => cell !== '' && !allowed.has(cell))

  if (unknown.length > 0) {
    return {
      ok: false,
      message: `Columnas no permitidas: ${uniqueLabels(unknown).join(', ')}.`
    }
  }

  const indexes: Record<string, number> = {}
  const missing: string[] = []
  const duplicated: string[] = []

  for (const column of columns) {
    const matches = header
      .map((cell, index) => ({ cell, index }))
      .filter(entry => column.aliases.has(entry.cell))

    if (matches.length === 0) {
      missing.push(column.label)
      continue
    }

    if (matches.length > 1) {
      duplicated.push(column.label)
      continue
    }

    indexes[column.key] = matches[0]!.index
  }

  if (missing.length > 0) {
    return {
      ok: false,
      message: `Faltan columnas obligatorias: ${missing.join(', ')}.`
    }
  }

  if (duplicated.length > 0) {
    return {
      ok: false,
      message: `Hay columnas duplicadas para: ${duplicated.join(', ')}.`
    }
  }

  if (header.filter(cell => cell !== '').length !== columns.length) {
    return {
      ok: false,
      message: `El CSV debe tener exactamente ${columns.length} columnas.`
    }
  }

  return { ok: true, indexes }
}

function failStudents(reason: string): CsvParseResult<ExamStudent> {
  return {
    ok: false,
    message: formatCsvError(
      'estudiantes',
      reason,
      STUDENTS_CSV_EXAMPLE,
      'codigo (o code, student_code, codigo_estudiante), nombre (o name, student_name, nombre_completo) y correo (o email, mail, correo_electronico)'
    )
  }
}

function failAnswers(reason: string): CsvParseResult<ExamAnswer> {
  return {
    ok: false,
    message: formatCsvError(
      'respuestas',
      reason,
      ANSWERS_CSV_EXAMPLE,
      'pregunta (o numero, nro, question, question_id), clave (o respuesta, correcta, correct_answer, answer) y puntaje (o puntos, points, score, valor, peso)'
    )
  }
}

function formatCsvError(
  kind: string,
  reason: string,
  example: string,
  aliases: string
): string {
  return [
    `El CSV de ${kind} no es válido. ${reason}`,
    '',
    'Debe verse así:',
    example,
    '',
    `Columnas aceptadas: ${aliases}.`
  ].join('\n')
}

function uniqueLabels(values: string[]): string[] {
  return [...new Set(values)]
}

function normalizeHeader(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
}

function parseCsv(text: string): string[][] {
  const normalized = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const rows: string[][] = []
  let current = ''
  let row: string[] = []
  let inQuotes = false

  for (let index = 0; index < normalized.length; index += 1) {
    const char = normalized[index]!
    const next = normalized[index + 1]

    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (char === ',' && !inQuotes) {
      row.push(current)
      current = ''
      continue
    }

    if (char === '\n' && !inQuotes) {
      row.push(current)
      rows.push(row)
      row = []
      current = ''
      continue
    }

    current += char
  }

  if (current.length > 0 || row.length > 0) {
    row.push(current)
    rows.push(row)
  }

  return rows.filter(cells => cells.some(cell => cell.trim() !== ''))
}

function serializeCsv(rows: string[][]): string {
  return `${rows.map(row => row.map(escapeCsvCell).join(',')).join('\n')}\n`
}

function escapeCsvCell(value: string): string {
  if (/[",\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`
  }

  return value
}
