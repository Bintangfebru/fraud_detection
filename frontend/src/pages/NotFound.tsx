import { useNavigate } from 'react-router-dom'
import { Shield, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-warm-100 dark:bg-navy-900 flex items-center justify-center p-4">
      <div className="text-center animate-fade-in">
        <div className="inline-flex w-16 h-16 rounded-2xl bg-navy-700 items-center justify-center mb-6">
          <Shield className="w-8 h-8 text-coral-400" />
        </div>
        <div className="font-display font-bold text-7xl text-navy-700 dark:text-warm-100 leading-none mb-2">
          404
        </div>
        <h1 className="font-display font-bold text-xl uppercase tracking-widest text-navy-700 dark:text-warm-200 mb-2">
          Page Not Found
        </h1>
        <p className="text-sm font-mono text-warm-500 dark:text-warm-400 mb-8">
          The page you're looking for doesn't exist or you don't have access.
        </p>
        <Button
          variant="primary"
          onClick={() => navigate('/dashboard')}
          icon={<ArrowLeft className="w-4 h-4" />}
        >
          Back to Dashboard
        </Button>
      </div>
    </div>
  )
}