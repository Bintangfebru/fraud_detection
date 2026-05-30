import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Shield, User, Eye, Ban, Edit2 } from 'lucide-react'
import { getUsers, createUser, updateUser, deactivateUser } from '@/api/users'
import { queryKeys } from '@/lib/queryKeys'
import { type Role } from '@/types/api'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { ErrorState, EmptyState } from '@/components/ui/ErrorState'
import { TableRowSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { formatDate, timeAgo } from '@/utils/format'
import { useAuthStore } from '@/stores/authStore'
import toast from 'react-hot-toast'

const ROLE_VARIANTS: Record<Role, 'fraud' | 'review' | 'info'> = {
  admin: 'fraud',
  analyst: 'review',
  auditor: 'info',
}

const ROLE_ICONS: Record<Role, React.ReactNode> = {
  admin: <Shield className="w-3 h-3" />,
  analyst: <Eye className="w-3 h-3" />,
  auditor: <User className="w-3 h-3" />,
}

export function Users() {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)

  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [editUserId, setEditUserId] = useState<string | null>(null)

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'analyst' as Role,
  })

  const [editForm, setEditForm] = useState<{
    role: Role
    is_active: boolean
  }>({ role: 'analyst', is_active: true })

  const users = useQuery({
    queryKey: queryKeys.users(page, 20),
    queryFn: ({ signal }) => getUsers(page, 20, { signal }),
  })

  const createMutation = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      toast.success(`User ${form.username} created`)
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setCreateOpen(false)
      setForm({ username: '', email: '', password: '', role: 'analyst' })
    },
    onError: () => toast.error('Failed to create user'),
  })

  const updateMutation = useMutation({
    mutationFn: (userId: string) => updateUser(userId, editForm),
    onSuccess: () => {
      toast.success('User updated')
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setEditUserId(null)
    },
    onError: () => toast.error('Failed to update user'),
  })

  const deactivateMutation = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => {
      toast.success('User deactivated')
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: () => toast.error('Failed to deactivate user'),
  })

  const editTarget = users.data?.items.find((u) => u.id === editUserId)
  const totalPages = users.data ? Math.ceil(users.data.total / 20) : 0

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── Role Summary ─────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        {(['admin', 'analyst', 'auditor'] as Role[]).map((role) => {
          const count = users.data?.items.filter((u) => u.role === role).length ?? 0
          return (
            <Card key={role} className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-warm-200 dark:bg-navy-700 flex items-center justify-center">
                <span className="text-navy-700 dark:text-warm-300">{ROLE_ICONS[role]}</span>
              </div>
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400">
                  {role}s
                </div>
                <div className="font-display font-bold text-2xl text-navy-700 dark:text-warm-200">
                  {users.isLoading ? <Skeleton className="h-6 w-8 mt-1" /> : count}
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {/* ── Table Header ─────────────────────────────────────── */}
      <Card noPad>
        <div className="flex items-center justify-between p-5">
          <CardHeader
            title="User Management"
            subtitle={users.data ? `${users.data.total} users` : '—'}
            className="mb-0"
          />
          <Button
            variant="primary"
            size="sm"
            icon={<UserPlus className="w-3.5 h-3.5" />}
            onClick={() => setCreateOpen(true)}
          >
            Add User
          </Button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-warm-200 dark:border-navy-700">
                {['Username', 'Email', 'Role', 'Status', 'Last Login', 'Created', ''].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.isLoading ? (
                Array.from({ length: 6 }).map((_, i) => <TableRowSkeleton key={i} cols={7} />)
              ) : users.isError ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12">
                    <ErrorState message="Failed to load users" onRetry={() => users.refetch()} />
                  </td>
                </tr>
              ) : users.data?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12">
                    <EmptyState
                      icon={<User className="w-6 h-6" />}
                      title="No users found"
                    />
                  </td>
                </tr>
              ) : (
                users.data?.items.map((user) => (
                  <tr
                    key={user.id}
                    className="border-b border-warm-200/60 dark:border-navy-700/50 hover:bg-warm-100 dark:hover:bg-navy-700/30 transition-colors"
                  >
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-md bg-navy-700 dark:bg-navy-600 flex items-center justify-center">
                          <span className="text-[10px] font-display font-bold text-warm-200 uppercase">
                            {user.username.charAt(0)}
                          </span>
                        </div>
                        <span className="font-semibold text-navy-700 dark:text-warm-200">
                          {user.username}
                          {user.id === currentUser?.id && (
                            <span className="ml-1 text-[9px] text-warm-400">(you)</span>
                          )}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-warm-500 dark:text-warm-400">{user.email}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant={ROLE_VARIANTS[user.role]}>
                        {user.role}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge variant={user.is_active ? 'safe' : 'neutral'} dot>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-warm-500 dark:text-warm-400">
                      {user.last_login ? timeAgo(user.last_login) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-warm-500 dark:text-warm-400">
                      {formatDate(user.created_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={<Edit2 className="w-3 h-3" />}
                          onClick={() => {
                            setEditUserId(user.id)
                            setEditForm({ role: user.role, is_active: user.is_active })
                          }}
                        >
                          Edit
                        </Button>
                        {user.id !== currentUser?.id && user.is_active && (
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={<Ban className="w-3 h-3" />}
                            className="text-coral-400 hover:text-coral-500"
                            onClick={() => deactivateMutation.mutate(user.id)}
                          >
                            Ban
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-warm-200 dark:border-navy-700">
            <span className="text-xs font-mono text-warm-500">
              Page {page} of {totalPages}
            </span>
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Prev
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* ── Create User Modal ─────────────────────────────────── */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create New User"
        size="sm"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={createMutation.isPending}
              disabled={!form.username || !form.email || !form.password}
              onClick={() => createMutation.mutate()}
            >
              Create User
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {[
            { label: 'Username', key: 'username', type: 'text', placeholder: 'john.doe' },
            { label: 'Email', key: 'email', type: 'email', placeholder: 'john@company.com' },
            { label: 'Password', key: 'password', type: 'password', placeholder: '••••••••' },
          ].map(({ label, key, type, placeholder }) => (
            <div key={key}>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-1.5">
                {label}
              </label>
              <input
                type={type}
                value={form[key as keyof typeof form]}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                placeholder={placeholder}
                className="w-full h-9 px-3 text-sm font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy-700/20 dark:focus:ring-coral-400/20 text-navy-700 dark:text-warm-100 placeholder:text-warm-400"
              />
            </div>
          ))}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-1.5">
              Role
            </label>
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as Role }))}
              className="w-full h-9 px-3 text-sm font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none text-navy-700 dark:text-warm-200"
            >
              <option value="analyst">Analyst</option>
              <option value="auditor">Auditor</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </div>
      </Modal>

      {/* ── Edit User Modal ───────────────────────────────────── */}
      <Modal
        open={!!editUserId && !!editTarget}
        onClose={() => setEditUserId(null)}
        title="Edit User"
        subtitle={editTarget?.username}
        size="sm"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setEditUserId(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={updateMutation.isPending}
              onClick={() => editUserId && updateMutation.mutate(editUserId)}
            >
              Save Changes
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-1.5">
              Role
            </label>
            <select
              value={editForm.role}
              onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value as Role }))}
              className="w-full h-9 px-3 text-sm font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none text-navy-700 dark:text-warm-200"
            >
              <option value="analyst">Analyst</option>
              <option value="auditor">Auditor</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="flex items-center gap-3">
            <input
              id="active-toggle"
              type="checkbox"
              checked={editForm.is_active}
              onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="w-4 h-4 rounded border-warm-300 accent-navy-700 dark:accent-coral-400"
            />
            <label
              htmlFor="active-toggle"
              className="text-xs font-mono text-navy-700 dark:text-warm-200"
            >
              Account Active
            </label>
          </div>
        </div>
      </Modal>
    </div>
  )
}