import { isAxiosError } from 'axios'

const API_DETAIL_MESSAGES: Record<string, string> = {
  'Email already registered': '邮箱已被注册，请换一个邮箱',
  'Username already registered': '用户名已被使用，请换一个用户名',
  'Registration conflicts with an existing record': '注册信息与已有账户冲突，请更换用户名或邮箱'
}

interface ApiErrorBody {
  detail?: unknown
}

export function getApiErrorMessage(error: unknown, fallback: string) {
  if (!isAxiosError(error)) {
    return fallback
  }

  const data = error.response?.data as ApiErrorBody | undefined
  const detail = data?.detail
  if (typeof detail !== 'string') {
    return fallback
  }

  return API_DETAIL_MESSAGES[detail] ?? detail
}
