import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react'
import { login } from '@/api/auth'
import { getMe } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/format'
import toast from 'react-hot-toast'

export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username || !password) return
    setError('')
    setLoading(true)
    try {
      const tokens = await login(username, password)
      const user = await getMe({ headers: { Authorization: `Bearer ${tokens.access_token}` } })
      setAuth(user, tokens.access_token, tokens.refresh_token)
      toast.success(`Welcome back, ${user.username}`)
      navigate('/dashboard')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen bg-sage-100 dark:bg-ink-900 flex items-center justify-center p-4 overflow-hidden">
      {/* Background blobs */}
      <div className="bg-blob" />
      <div className="bg-blob-extra" />

      <div className="relative z-10 w-full max-w-sm animate-slide-up">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 rounded-3xl bg-ink-700/90 dark:bg-coral-400/90 items-center justify-center mb-5 shadow-xl">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="font-display text-4xl text-ink-800 dark:text-white leading-tight tracking-tight">
            FraudShield
          </h1>
          <p className="text-xs font-mono text-stone-400 dark:text-white/35 mt-2 uppercase tracking-widest">
            Enterprise Fraud Detection
          </p>
        </div>

        {/* Glass card */}
        <div className="glass-card p-7">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-widest text-stone-400 dark:text-white/35 mb-2">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                className="glass-input w-full h-11 px-4 text-sm font-body text-ink-800 dark:text-white placeholder:text-stone-300 dark:placeholder:text-white/20"
                placeholder="admin"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase tracking-widest text-stone-400 dark:text-white/35 mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className="glass-input w-full h-11 px-4 pr-11 text-sm font-body text-ink-800 dark:text-white placeholder:text-stone-300 dark:placeholder:text-white/20"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-300 hover:text-stone-500 dark:hover:text-white/50 transition-colors"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-xs font-mono text-coral-400 bg-coral-400/08 border border-coral-400/20 rounded-xl px-4 py-2.5">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username || !password}
              className={cn(
                'btn-primary w-full h-11 font-body font-medium text-sm',
                'flex items-center justify-center gap-2',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Authenticating…</>
              ) : (
                'Sign In'
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-[10px] font-mono text-stone-300 dark:text-white/20 mt-6 uppercase tracking-widest">
          FraudShield v3.0 — Secure Access
        </p>
      </div>
    </div>
  )
}