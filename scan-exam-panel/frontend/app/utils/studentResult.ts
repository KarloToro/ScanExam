export type StudentResultAnswer = {
  question_id: number
  detected_answer: unknown
  correct_answer: string
  question_status: string
  points: number
  earned_points: number
}

export type StudentResult = {
  exam_name: string
  student_name?: string
  score: number | null
  max_score: number | null
  percentage: number | null
  answers: StudentResultAnswer[]
}

export function formatDetectedAnswer(value: unknown): string {
  if (value == null) {
    return '—'
  }
  if (typeof value === 'string') {
    return value || '—'
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  try {
    return JSON.stringify(value)
  } catch {
    return '—'
  }
}
