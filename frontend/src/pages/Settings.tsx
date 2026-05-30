import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Sun, Moon, Monitor, Save, Key, Bell, Shield } from 'lucide-react'
import { changePassword } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'
import { useThemeStore } from '@/stores/themeStore'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { cn } from '@/utils/format'
import toast from 'react-hot-toast'

type ThemeOption = 'light' | 'dark'

export function Settings() {
  const user = useAuthStore((s) => s.user)
  const { theme, setTheme } = useThemeStore()

  const [pwForm, setPwForm] = useState({
    current: '',
    next: '',
    confirm: '',
  })
  const [pwError, setPwError] = useState('')

  const changePwMutation = useMutation({
    mutationFn: () => changePassword(pwForm.current, pwForm.next),
    onSuccess: () => {
      toast.success('Password changed successfully')
      setPwForm({ current: '', next: '', confirm: '' })
    },
    onError: () => {
      setPwError('Current password is incorrect or server error')
    },
  })

  const handleChangePw = () => {
    setPwError('')
    if (!pwForm.current || !pwForm.next) {
      setPwError('Please fill all fields')
      return
    }
    if (pwForm.next !== pwForm.confirm) {
      setPwError('New passwords do not match')
      return
    }
    if (pwForm.next.length < 8) {
      setPwError('Password must be at least 8 characters')
      return
    }
    changePwMutation.mutate()
  }

  const themeOptions: { value: ThemeOption; label: string; icon: React.ReactNode }[] = [
    { value: 'light', label: 'Light', icon: <Sun className="w-4 h-4" /> },
    { value: 'dark', label: 'Dark', icon: <Moon className="w-4 h-4" /> },
  ]

  return (
    <div className="max-w-2xl space-y-6 animate-fade-in">
      {/* ── Profile ──────────────────────────────────────────── */}
      <Card>
        <CardHeader title="Profile" subtitle="Your account information" />
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl bg-navy-700 flex items-center justify-center flex-shrink-0">
            <span className="font-display font-bold text-xl text-warm-100 uppercase">
              {user?.username?.charAt(0) ?? '?'}
            </span>
          </div>
          <div>
            <div className="font-display font-bold text-lg text-navy-700 dark:text-warm-100 uppercase tracking-wide">
              {user?.username}
            </div>
            <div className="text-xs font-mono text-warm-500 dark:text-warm-400">
              {user?.email}
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <Shield className="w-3 h-3 text-coral-400" />
              <span className="text-[10px] font-mono uppercase tracking-wider text-coral-400">
                {user?.role}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* ── Appearance ───────────────────────────────────────── */}
      <Card>
        <CardHeader title="Appearance" subtitle="Customize the interface theme" />
        <div className="flex gap-3">
          {themeOptions.map(({ value, label, icon }) => (
            <button
              key={value}
              onClick={() => setTheme(value)}
              className={cn(
                'flex-1 flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all',
                theme === value
                  ? 'border-navy-700 dark:border-coral-400 bg-navy-700/5 dark:bg-coral-400/10'
                  : 'border-warm-300 dark:border-navy-600 hover:border-warm-400 dark:hover:border-navy-500',
              )}
            >
              <span
                className={cn(
                  theme === value
                    ? 'text-navy-700 dark:text-coral-400'
                    : 'text-warm-500 dark:text-warm-400',
                )}
              >
                {icon}
              </span>
              <span
                className={cn(
                  'text-xs font-mono uppercase tracking-wider',
                  theme === value
                    ? 'text-navy-700 dark:text-coral-400 font-semibold'
                    : 'text-warm-500 dark:text-warm-400',
                )}
              >
                {label}
              </span>
              {theme === value && (
                <div className="w-1.5 h-1.5 rounded-full bg-navy-700 dark:bg-coral-400" />
              )}
            </button>
          ))}
        </div>
      </Card>

      {/* ── Change Password ───────────────────────────────────── */}
      <Card>
        <CardHeader
          title="Security"
          subtitle="Change your account password"
          action={<Key className="w-4 h-4 text-warm-400" />}
        />
        <div className="space-y-3">
          {[
            { label: 'Current Password', key: 'current' },
            { label: 'New Password', key: 'next' },
            { label: 'Confirm New Password', key: 'confirm' },
          ].map(({ label, key }) => (
            <div key={key}>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-1.5">
                {label}
              </label>
              <input
                type="password"
                value={pwForm[key as keyof typeof pwForm]}
                onChange={(e) =>
                  setPwForm((f) => ({ ...f, [key]: e.target.value }))
                }
                placeholder="••••••••"
                className="w-full h-9 px-3 text-sm font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy-700/20 dark:focus:ring-coral-400/20 text-navy-700 dark:text-warm-100 placeholder:text-warm-400"
              />
            </div>
          ))}

          {pwError && (
            <div className="text-xs font-mono text-coral-400 bg-coral-50 dark:bg-coral-600/10 border border-coral-100 dark:border-coral-600/20 rounded-lg px-3 py-2">
              {pwError}
            </div>
          )}

          <Button
            variant="primary"
            size="sm"
            loading={changePwMutation.isPending}
            icon={<Save className="w-3.5 h-3.5" />}
            onClick={handleChangePw}
          >
            Update Password
          </Button>
        </div>
      </Card>

      {/* ── Notification Preferences ──────────────────────────── */}
      <Card>
        <CardHeader
          title="Notifications"
          subtitle="Alert and notification preferences"
          action={<Bell className="w-4 h-4 text-warm-400" />}
        />
        <div className="space-y-3">
          {[
            { label: 'High-risk fraud alerts', desc: 'Notify when fraud score > 0.8', key: 'highRisk', default: true },
            { label: 'Review queue updates', desc: 'Notify when new items need review', key: 'reviewQueue', default: true },
            { label: 'System health alerts', desc: 'Notify on system degradation', key: 'health', default: false },
            { label: 'Model performance reports', desc: 'Weekly model performance digest', key: 'modelReports', default: false },
          ].map(({ label, desc, key, default: def }) => {
            const [checked, setChecked] = useState(def)
            return (
              <div key={key} className="flex items-center justify-between py-2 border-b border-warm-200/60 dark:border-navy-700/50 last:border-0">
                <div>
                  <div className="text-xs font-mono text-navy-700 dark:text-warm-200">{label}</div>
                  <div className="text-[10px] font-mono text-warm-400 mt-0.5">{desc}</div>
                </div>
                <button
                  onClick={() => setChecked((c) => !c)}
                  className={cn(
                    'relative w-10 h-5 rounded-full transition-colors',
                    checked ? 'bg-navy-700 dark:bg-coral-400' : 'bg-warm-300 dark:bg-navy-600',
                  )}
                >
                  <div
                    className={cn(
                      'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                      checked ? 'translate-x-5' : 'translate-x-0.5',
                    )}
                  />
                </button>
              </div>
            )
          })}
        </div>
      </Card>

      {/* ── System Info ───────────────────────────────────────── */}
      <Card>
        <CardHeader title="System Information" subtitle="FraudShield platform details" />
        <div className="grid grid-cols-2 gap-3 text-xs font-mono">
          {[
            ['Version', 'v3.0.0'],
            ['Environment', import.meta.env.MODE ?? 'production'],
            ['API Base', import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'],
            ['Build', new Date().toLocaleDateString('id-ID')],
          ].map(([k, v]) => (
            <div key={k}>
              <div className="text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-0.5">{k}</div>
              <div className="text-navy-700 dark:text-warm-200 font-semibold truncate">{v}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}