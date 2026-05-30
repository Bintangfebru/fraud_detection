import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
  toggle: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'light',
      setTheme: (theme) => {
        set({ theme })
        applyTheme(theme)
      },
      toggle: () => {
        const next: Theme = get().theme === 'light' ? 'dark' : 'light'
        set({ theme: next })
        applyTheme(next)
      },
    }),
    { name: 'fraudshield-theme' },
  ),
)

function applyTheme(theme: Theme) {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

// Apply theme immediately on store rehydration
useThemeStore.subscribe((state) => applyTheme(state.theme))
